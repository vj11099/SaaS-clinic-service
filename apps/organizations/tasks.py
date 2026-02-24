from celery import shared_task
from django_tenants.utils import schema_context
from django.db import transaction
from utils.registration_mail import (
    send_registration_email, send_verification_email
)
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def register_organization_async(self, validated_data):
    """
    Full organization setup pipeline:
    1. Create organization (tenant + schema)
    2. Create domain
    3. Send registration email
    4. Create admin user
    5. Assign subscription plan
    6. Send verification email

    Cleanup on failure: org + domain + schema are deleted before retry.
    """
    organization = None

    try:
        # Registration email (inform user organization is being set up)
        send_registration_email(
            validated_data['username'],
            validated_data['contact_email']
        )

        organization = _create_organization(validated_data)
        _create_domain(organization)

        with transaction.atomic():
            admin_user, generated_password = _create_admin_user(
                organization, validated_data
            )
            _assign_subscription_plan(
                organization, validated_data['email']
            )

        # Verification email with credentials
        send_verification_email(admin_user, generated_password)

        logger.info(
            f"[{organization.schema_name}] Organization setup completed — "
            f"admin: {admin_user.username}"
        )

    except Exception as exc:
        # Cleanup: wipe org, domain, and schema before retrying
        # so we don't end up with orphaned tenants
        _cleanup_organization(organization)

        logger.error(
            f"register_organization_async failed for "
            f"schema='{validated_data.get('organization_schema_name')}' "
            f"(attempt {self.request.retries +
                        1}/{self.max_retries + 1}): {exc}",
            exc_info=True
        )

        try:
            raise self.retry(exc=exc, countdown=2 **
                             self.request.retries)
        except self.MaxRetriesExceededError:
            logger.critical(
                f"[CRITICAL] register_organization_async permanently failed for "
                f"schema='{validated_data.get('organization_schema_name')}' "
                f"after {self.max_retries + 1} attempts. "
                f"Manual intervention required. Last error: {exc}",
                exc_info=True
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_organization(validated_data):
    from .models import Organization

    return Organization.objects.create(
        name=validated_data['organization_name'],
        schema_name=validated_data['organization_schema_name'],
        contact_email=validated_data['contact_email'],
        contact_phone=validated_data.get('contact_phone', ''),
        is_active=True
    )


def _create_domain(organization):
    import os
    from .models import Domain

    primary_domain = os.getenv('DOMAIN')
    if not primary_domain:
        raise Exception(
            'DOMAIN environment variable not set. '
            'Please add DOMAIN to your .env file.'
        )

    return Domain.objects.create(
        domain=f"{organization.schema_name}.{primary_domain}",
        tenant=organization,
        is_primary=True,
    )


def _create_admin_user(organization, validated_data):
    from ..users.models import User, Role, UserRole

    with schema_context(organization.schema_name):
        admin_user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            is_superuser=validated_data.get('is_superuser', False),
            is_tenant_admin=validated_data.get('is_tenant_admin', True),
            is_staff=validated_data.get('is_staff', False),
        )
        generated_password = admin_user.generate_password()

        admin_role = Role.objects.get(name='superuser', is_system_role=True)
        UserRole.objects.get_or_create(
            user=admin_user,
            role=admin_role,
            defaults={'is_active': True, 'is_deleted': False}
        )

        return admin_user, generated_password


def _assign_subscription_plan(organization, user_email):
    from ..subscriptions.models import SubscriptionPlan
    from ..subscriptions.services import SubscriptionService

    try:
        plan = SubscriptionPlan.objects.get(
            slug='trial', is_active=True, is_public=True)
    except SubscriptionPlan.DoesNotExist:
        plan = SubscriptionPlan.objects.filter(
            price=0, is_active=True, is_public=True
        ).first()
        if not plan:
            raise Exception(
                "No default trial plan found. "
                "Please create a plan with slug 'trial' or a free plan."
            )

    SubscriptionService.subscribe(
        organization=organization,
        plan=plan,
        performed_by_email=user_email
    )


def _cleanup_organization(organization):
    """
    Delete org, domain, and tenant schema on failure.
    Safe to call even if org is None (e.g. failed before org was created).
    """
    if organization is None:
        return

    try:
        # django-tenants cascades domain deletion and drops the schema
        # when the tenant is deleted, as long as AUTO_DROP_SCHEMA = True
        organization.delete()
        logger.warning(
            f"Cleanup: deleted org + schema '{organization.schema_name}'"
        )
    except Exception as cleanup_exc:
        # Cleanup itself failed
        logger.critical(
            f"[CRITICAL] Cleanup failed for schema='{
                organization.schema_name}': "
            f"{cleanup_exc}. Orphaned tenant may exist — manual cleanup required.",
            exc_info=True
        )
