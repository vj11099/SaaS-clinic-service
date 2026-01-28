from rest_framework.throttling import UserRateThrottle
from django.db import connection


class TenantUserRateThrottle(UserRateThrottle):
    scope = 'tenant_user'

    def get_cache_key(self, request, view):
        if not request.user.is_authenticated:
            return None

        # Key format: throttle_schemaName_userId
        return self.cache_format % {
            'scope': self.scope,
            'ident': f"{connection.schema_name}_{request.user.pk}"
        }
