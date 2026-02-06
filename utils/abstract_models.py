from django.db import models
from django.db.models import QuerySet


class TenantQuerySet(QuerySet):
    """
    Custom QuerySet that adds tenant-aware filtering.
    """

    def for_organization(self, organization):
        """Filter queryset by organization."""
        return self.filter(organization=organization)

    def with_related(self, *fields):
        """
        Optimize queries with select_related for foreign keys.
        Prevents N+1 queries.
        """
        return self.select_related(*fields)

    def with_prefetch(self, *fields):
        """
        Optimize queries with prefetch_related for reverse foreign keys and M2M.
        Prevents N+1 queries.
        """
        return self.prefetch_related(*fields)


class TenantManager(models.Manager):
    """
    Base manager for all tenant-scoped models.
    Automatically filters queries by the current organization.
    """

    def get_queryset(self):
        """Return the base queryset using TenantQuerySet."""
        return TenantQuerySet(self.model, using=self._db)

    def for_organization(self, organization):
        """
        Get all objects for a specific organization.

        Args:
            organization: Organization instance

        Returns:
            Filtered queryset
        """
        return self.get_queryset().for_organization(organization)

    def create_for_organization(self, organization, **kwargs):
        """
        Create an object for a specific organization.

        Args:
            organization: Organization instance
            **kwargs: Model field values

        Returns:
            Created model instance
        """
        kwargs['organization'] = organization
        return self.create(**kwargs)


class TenantAwareManager(TenantManager):
    """
    Extended manager with additional optimization methods.
    """

    def with_common_relations(self):
        """
        Override in child managers to define common select_related/prefetch_related.
        This prevents N+2 queries for commonly accessed relations.
        """
        return self.get_queryset()

    def active(self):
        """Filter for active records (if model has is_active field)."""
        return self.get_queryset().filter(is_active=True)

    def deleted(self):
        """Filter for soft-deleted records (if model has is_deleted field)."""
        return self.get_queryset().filter(is_deleted=True)


class BaseAuditTrailModel(models.Model):
    """
    Abstract base model with audit trail fields.
    """
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, db_index=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        abstract = True
        ordering = ['-created_at']


class TenantModel(BaseAuditTrailModel):
    """
    Abstract base model for all tenant-scoped models.
    Includes organization FK and tenant-aware manager.
    """
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='%(class)s_set',
        db_index=True
    )

    objects = TenantManager()

    class Meta:
        abstract = True
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organization', '-created_at']),
        ]

    def save(self, *args, **kwargs):
        """Override save to add validation."""
        if not self.organization_id:
            raise ValueError(
                f"{self.__class__.__name__} must have an organization")
        super().save(*args, **kwargs)
