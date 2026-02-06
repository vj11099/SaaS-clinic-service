import secrets
from django.utils import timezone
from django.contrib.auth.hashers import check_password
from datetime import timedelta
from django.contrib.postgres.fields import ArrayField
from django.core.validators import RegexValidator
from django.contrib.auth.models import AbstractUser
from django.db import models
from .roles_and_permissions import Role, Permission


class User(AbstractUser):
    """
    User model - Both PUBLIC & TENANT schema
    For users from public schema and organizations
    """
    email = models.EmailField(unique=True)
    phone_validator = RegexValidator(
        regex=r'^\d{10}$',
        message="Phone number must be exactly 10 digits (e.g., 1234567890)."
    )
    phone = models.CharField(
        null=True,
        blank=True,
        max_length=10,
        validators=[phone_validator],
    )

    is_tenant_admin = models.BooleanField(default=False)
    # add roles later

    is_active = models.BooleanField(default=True)

    password_generated_at = models.DateTimeField(
        auto_now=True, null=True, blank=True
    )
    password_verified = models.BooleanField(default=False)
    previous_passwords = ArrayField(
        models.CharField(max_length=128),
        size=3,
        null=True
    )

    # Audit trail
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login_at = models.DateTimeField(null=True, blank=True)

    roles = models.ManyToManyField(
        Role,
        through='UserRole',
        related_name='users',
        blank=True
    )

    def get_all_permissions(self):
        """Get all permissions from all user's roles"""
        # permissions = set()
        # for user_role in self.user_roles.select_related('role').all():
        #     if user_role.role.is_active and not user_role.role.is_deleted:
        #         role_perms = user_role.role.get_permissions_list()
        #         permissions.update(role_perms)
        # return list(permissions)
        #
        # discarded due to N + 1

        # Prefetch active roles with their active permissions
        #
        # active_role_prefetch = Prefetch(
        #     'user_roles',
        #     queryset=UserRole.objects.select_related('role').filter(
        #         role__is_active=True,
        #         role__is_deleted=False
        #     ).prefetch_related(
        #         Prefetch(
        #             'role__permissions',
        #             queryset=Permission.objects.filter(
        #                 is_active=True,
        #                 is_deleted=False
        #             )
        #         )
        #     )
        # )
        #
        # user_roles = self.user_roles.prefetch_related(active_role_prefetch)
        #
        # permissions = set()
        # for user_role in user_roles:
        #     permissions.update(
        #         user_role.role.permissions.values_list('name', flat=True)
        #     )
        # return list(permissions)
        #
        # discarded due to possible reverse query

        return list(Permission.objects.filter(
            # 1. Filter the Permission itself
            is_active=True,
            is_deleted=False,

            # 2. Join to Role (related_name='roles_permission' in Permission model)
            roles_permission__is_active=True,
            roles_permission__is_deleted=False,

            # 3. Join to UserRole (related_name='user_roles' in Role model)
            # We filter by 'user' here to ensure we only get this user's roles
            roles_permission__user_roles__user=self,

            # 4. (Optional) Filter the UserRole intermediate table for soft-deletes
            roles_permission__user_roles__is_active=True,
            roles_permission__user_roles__is_deleted=False

        ).values_list('name', flat=True).distinct())

    def has_permission(self, permission_name):
        """Check if user has a specific permission"""
        return permission_name in self.get_all_permissions()

    def has_any_permission(self, permission_names):
        """Check if user has any of the listed permissions"""
        user_perms = set(self.get_all_permissions())
        return bool(user_perms.intersection(set(permission_names)))

    def has_all_permissions(self, permission_names):
        """Check if user has all of the listed permissions"""
        user_perms = set(self.get_all_permissions())
        return set(permission_names).issubset(user_perms)

    class Meta:
        db_table = 'auth_user'
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['username']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.email} ({self.username})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.username

    def generate_password(self):
        """
        Generates a random temporary password
        """
        generated_password = secrets.token_urlsafe(10)
        self.set_password(generated_password)
        self.password_generated_at = timezone.now()
        self.previous_passwords = [self.password]
        self.is_active = False
        self.save()
        return generated_password

    def is_password_updated(self, expiry=24*60*60):
        if not self.password_verified:
            return True
        return False

    def is_password_valid(self, expiry=24*60*60):
        """
        check if the reset password time has expired
        """
        expiry_time = self.password_generated_at + \
            timedelta(seconds=expiry)
        if timezone.now() > expiry_time:
            return False
        return True

    def is_password_previously_used(self, raw_password):
        """
        check if the password was used from the last 3 passwords
        """
        if self.previous_passwords is None:
            return False
        for hash in self.previous_passwords:
            if check_password(raw_password, hash):
                return True
        return False

    # self explanatory
    def verify_user(self):
        self.password_verified = True
        self.is_active = True
        self.password_generated_at = None
        self.save()
        return self

    def update_password(self, raw_password):
        """
        Update the new password and
        Add the current passwords to previously used passwords
        """
        self.set_password(raw_password)

        if self.previous_passwords is None:
            self.previous_passwords = []
        self.previous_passwords.insert(0, self.password)
        self.previous_passwords = self.previous_passwords[:3]
        self.save()
        return self
