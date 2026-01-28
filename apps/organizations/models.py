from django.db import models
from django_tenants.models import TenantMixin, DomainMixin


class Organization(TenantMixin):
    name = models.CharField(max_length=255)
    schema_name = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=20, blank=True, null=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    max_users = models.IntegerField(default=10)

    class Meta:
        db_table = 'organizations'

    def __str__(self):
        return self.name

    auto_create_schema = True


class Domain(DomainMixin):
    class Meta:
        db_table = 'domains'

    def __str__(self):
        return self.domain
