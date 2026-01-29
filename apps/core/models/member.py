from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver


class Member(models.Model):
    """
    Member model - TENANT schema
    Each tenant has its own set of members
    """

    ROLE_CHOICES = [
        ('owner', 'Owner'),
        ('admin', 'Admin'),
        ('member', 'Member'),
        ('guest', 'Guest'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='memberships'
    )
    role = models.CharField(
        max_length=20, choices=ROLE_CHOICES, default='member'
    )
    is_active = models.BooleanField(default=True)
    invited_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invited_members'
    )
    invitation_accepted_at = models.DateTimeField(null=True, blank=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_member'
        unique_together = ['user']
        ordering = ['-joined_at']

    def __str__(self):
        return f"{self.user.email} - {self.role}"


# Signal handlers to update tenant member count
@receiver(post_save, sender=Member)
def update_member_count_on_save(sender, instance, created, **kwargs):
    """Update tenant's member count when a member is added"""
    if created and instance.is_active:
        from django_tenants.utils import schema_context, get_tenant_model
        from django.db import connection

        # Get current tenant
        tenant = connection.tenant

        # Switch to public schema to update tenant
        with schema_context('public'):
            Tenant = get_tenant_model()
            tenant_obj = Tenant.objects.get(schema_name=tenant.schema_name)

            # Count active members in tenant schema
            with schema_context(tenant.schema_name):
                active_count = Member.objects.filter(is_active=True).count()

            # Update count in public schema
            tenant_obj.current_member_count = active_count
            tenant_obj.save(update_fields=['current_member_count'])


@receiver(post_delete, sender=Member)
def update_member_count_on_delete(sender, instance, **kwargs):
    """Update tenant's member count when a member is deleted"""
    from django_tenants.utils import schema_context, get_tenant_model
    from django.db import connection

    # Get current tenant
    tenant = connection.tenant

    # Switch to public schema to update tenant
    with schema_context('public'):
        Tenant = get_tenant_model()
        tenant_obj = Tenant.objects.get(schema_name=tenant.schema_name)

        # Count remaining active members in tenant schema
        with schema_context(tenant.schema_name):
            active_count = Member.objects.filter(is_active=True).count()

        # Update count in public schema
        tenant_obj.current_member_count = active_count
        tenant_obj.save(update_fields=['current_member_count'])


@receiver(post_save, sender=Member)
def update_member_count_on_status_change(sender, instance, created, **kwargs):
    """Update count when member status changes"""
    if not created:  # Only for updates
        from django_tenants.utils import schema_context, get_tenant_model
        from django.db import connection

        tenant = connection.tenant

        with schema_context('public'):
            Tenant = get_tenant_model()
            tenant_obj = Tenant.objects.get(schema_name=tenant.schema_name)

            with schema_context(tenant.schema_name):
                active_count = Member.objects.filter(is_active=True).count()

            tenant_obj.current_member_count = active_count
            tenant_obj.save(update_fields=['current_member_count'])
