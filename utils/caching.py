from functools import wraps
from typing import Callable, Optional, Union
from django.core.cache import cache
from django.db import connection
import hashlib
import json
# import logging

# logger = logging.getLogger(__name__)


# ========================================================================
# UNIVERSAL CACHE DECORATOR
# ========================================================================

def cached(
    key: Optional[Union[str, Callable]] = None,
    timeout: int = 900,
    key_builder: Optional[Callable] = None,
    tenant_aware: bool = True,
    include_params: bool = True,
    namespace: Optional[str] = None
):
    """
    Universal caching decorator that works EVERYWHERE.

    Args:
        key: Cache key template or function to build key
             - String: "user_perms:{id}" or "patient_list"
             - Callable: lambda self, *args, **kwargs: f"custom_key_{self.id}"
             - None: Auto-generate from function name and params

        timeout: Cache TTL in seconds (default 900 = 15 min)

        key_builder: Custom function to build cache key
                     Signature: (func, instance, args, kwargs) -> str

        tenant_aware: Include tenant schema in key (default True)

        include_params: Include function parameters in key (default True)

        namespace: Optional namespace prefix for grouping related keys

    Usage Examples:

        # Model method with simple key template
        @cached("user_perms:{id}")
        def get_all_permissions(self):
            ...

        # Standalone function with auto-generated key
        @cached(timeout=600)
        def get_active_patients(clinic_id):
            ...

        # Custom key builder
        @cached(key_builder=lambda f, inst, args, kw: f"custom_{inst.id}_{args[0]}")
        def custom_method(self, param):
            ...

        # Serializer method
        @cached("patient_summary:{instance.id}", timeout=300)
        def get_medical_summary(self, instance):
            ...

        # View method
        @cached("patient_list:{request.user.id}", timeout=600)
        def list(self, request):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Determine context (self, cls, or standalone)
            instance = args[0] if args and hasattr(
                args[0], '__class__') else None

            # Build cache key
            if key_builder:
                # Custom key builder function
                cache_key = key_builder(func, instance, args, kwargs)
            elif callable(key):
                # Key is a lambda/function
                cache_key = key(*args, **kwargs)
            elif isinstance(key, str):
                # Key is a string template
                cache_key = _build_key_from_template(
                    key, func, instance, args, kwargs, include_params
                )
            else:
                # Auto-generate key
                cache_key = _auto_generate_key(
                    func, instance, args, kwargs, include_params
                )

            # Add namespace if provided
            if namespace:
                cache_key = f"{namespace}:{cache_key}"

            # Add tenant schema if enabled
            if tenant_aware:
                schema = _get_tenant_schema()
                cache_key = f"tenant:{schema}:{cache_key}"

            # Try to get from cache
            result = cache.get(cache_key)
            if result is not None:
                print(f"Cache HIT: {cache_key}")
                return result

            # Cache miss - execute function
            print(f"Cache MISS: {cache_key}")
            result = func(*args, **kwargs)

            # Convert queryset to list if needed
            if hasattr(result, 'model'):
                result = list(result)

            # Store in cache
            cache.set(cache_key, result, timeout=timeout)

            return result

        # Add helper methods to the wrapper
        wrapper.cache_key = key
        wrapper.cache_timeout = timeout
        wrapper.invalidate = lambda *args, **kwargs: _invalidate_cache(
            key, key_builder, func, args, kwargs, tenant_aware, namespace, include_params
        )

        return wrapper

    return decorator


# ========================================================================
# HELPER FUNCTIONS
# ========================================================================

def _get_tenant_schema():
    """Get current tenant schema"""
    schema_name = getattr(connection, 'schema_name', None)
    return schema_name if schema_name else 'public'


def _build_key_from_template(template, func, instance, args, kwargs, include_params):
    """Build cache key from string template"""

    # Extract variables from template (e.g., {id}, {instance.id}, {request.user.id})
    import re
    placeholders = re.findall(r'\{([^}]+)\}', template)

    context = {}

    # Add instance attributes
    if instance:
        context['id'] = getattr(instance, 'id', None)
        context['instance'] = instance
        context['self'] = instance

    # Add args and kwargs to context
    if args:
        # Try to map common parameter names
        if len(args) > 1:
            context['request'] = args[1] if hasattr(args[1], 'user') else None

    for key, value in kwargs.items():
        context[key] = value

    # Replace placeholders
    key_str = template
    for placeholder in placeholders:
        try:
            # Handle nested attributes (e.g., instance.id, request.user.id)
            value = _resolve_placeholder(placeholder, context)
            key_str = key_str.replace(f"{{{placeholder}}}", str(value))
        except (AttributeError, KeyError, IndexError):
            # Placeholder not found, keep as is or use hash
            pass

    # Add parameter hash if enabled and not all placeholders resolved
    if include_params and (args[1:] or kwargs):
        params_hash = _hash_params(args[1:] if instance else args, kwargs)
        key_str = f"{key_str}:{params_hash}"

    return key_str


def _resolve_placeholder(placeholder, context):
    """Resolve nested placeholder like 'instance.id' or 'request.user.id'"""
    parts = placeholder.split('.')
    value = context.get(parts[0])

    for part in parts[1:]:
        if value is None:
            break
        value = getattr(value, part, None)

    return value


def _auto_generate_key(func, instance, args, kwargs, include_params):
    """Auto-generate cache key from function name and parameters"""

    key_parts = [func.__name__]

    # Add instance ID if available
    if instance and hasattr(instance, 'id'):
        key_parts.append(str(instance.id))

    # Add parameter hash
    if include_params:
        func_args = args[1:] if instance else args
        if func_args or kwargs:
            params_hash = _hash_params(func_args, kwargs)
            key_parts.append(params_hash)

    return ':'.join(key_parts)


def _hash_params(args, kwargs):
    """Generate hash from function parameters"""
    params_data = {
        'args': [str(a) for a in args],
        'kwargs': {k: str(v) for k, v in sorted(kwargs.items())}
    }
    params_str = json.dumps(params_data, sort_keys=True, default=str)
    return hashlib.md5(params_str.encode()).hexdigest()[:12]


def _invalidate_cache(key, key_builder, func, args, kwargs, tenant_aware, namespace, include_params):
    """Invalidate the cache for this function call"""
    instance = args[0] if args and hasattr(args[0], '__class__') else None

    # Build the same cache key
    if key_builder:
        cache_key = key_builder(func, instance, args, kwargs)
    elif callable(key):
        cache_key = key(*args, **kwargs)
    elif isinstance(key, str):
        cache_key = _build_key_from_template(
            key, func, instance, args, kwargs, include_params
        )
    else:
        cache_key = _auto_generate_key(
            func, instance, args, kwargs, include_params
        )

    if namespace:
        cache_key = f"{namespace}:{cache_key}"

    if tenant_aware:
        schema = _get_tenant_schema()
        cache_key = f"tenant:{schema}:{cache_key}"

    cache.delete(cache_key)
    print(f"Cache invalidated: {cache_key}")


# ========================================================================
# CONVENIENCE ALIASES
# ========================================================================

# For those who prefer specific names
cached_method = cached  # Alias for model methods
cached_function = cached  # Alias for standalone functions
cached_property = cached  # Alias for properties


# ========================================================================
# GENERIC INVALIDATE HELPER
# ========================================================================

def invalidate_cache(key_template, tenant_aware=True, namespace=None, **template_vars):
    """
    Generic cache invalidation helper.

    Args:
    key_template: Cache key template (e.g., "user_perms:{user_id}")
    tenant_aware: Include tenant schema (default True)
    namespace: Optional namespace prefix
    **template_vars: Variables to fill template (e.g., user_id=123)

    Usage:
    invalidate_cache("user_perms:{user_id}", user_id=123)
    invalidate_cache("patient_list:{clinic_id}", clinic_id=456)
    invalidate_cache("stats:{id}", namespace="clinic", id=789)
    """
    # Fill template
    cache_key = key_template.format(**template_vars)

    # Add namespace
    if namespace:
        cache_key = f"{namespace}:{cache_key}"

    # Add tenant
    if tenant_aware:
        schema = _get_tenant_schema()
        cache_key = f"tenant:{schema}:{cache_key}"

    cache.delete(cache_key)
    print(f"Cache invalidated: {cache_key}")


def invalidate_cache_pattern(*key_parts, tenant_aware=True, namespace=None):
    """
    Invalidate cache using key parts.

    Usage:
    invalidate_cache_pattern("user_perms", user_id)
    invalidate_cache_pattern("clinic", "stats", clinic_id)
    """
    cache_key = ':'.join(str(p) for p in key_parts)

    if namespace:
        cache_key = f"{namespace}:{cache_key}"

    if tenant_aware:
        schema = _get_tenant_schema()
        cache_key = f"tenant:{schema}:{cache_key}"

    cache.delete(cache_key)
    print(f"Cache invalidated: {cache_key}")


# ========================================================================
# BULK INVALIDATION HELPER
# ========================================================================

def invalidate_multiple(key_templates, tenant_aware=True, namespace=None, **template_vars):
    """
    Invalidate multiple cache keys at once.

    Usage:
    invalidate_multiple(
        ["user_perms:{user_id}", "user_roles:{user_id}"],
        user_id=123
    )
    """
    for template in key_templates:
        invalidate_cache(template, tenant_aware=tenant_aware,
                         namespace=namespace, **template_vars)

# ========================================================================
# CACHE CONFIGURATION
# ========================================================================


class CacheConfig:
    """Central cache configuration"""

    # Default TTLs (in seconds)
    DEFAULT_TTL = 900  # 15 minutes
    SHORT_TTL = 300    # 5 minutes
    LONG_TTL = 1800    # 30 minutes

    # Cache key templates
    USER_PERMISSIONS = "user_perms:{id}"
    USER_ROLES = "user_roles:{id}"
    ROLE_PERMISSIONS = "role_perms:{id}"


# ========================================================================
# USAGE EXAMPLES
# ========================================================================

"""
# ============================================================================
# EXAMPLE 1: Model Methods
# ============================================================================

from dynamic_cache import cached

class User(AbstractUser):

    # Simple template with {id}
    @cached("user_perms:{id}", timeout=900)
    def get_all_permissions(self):
        return list(Permission.objects.filter(...))

    # Auto-generated key (uses function name + id)
    @cached(timeout=600)
    def get_active_roles(self):
        return list(self.roles.filter(is_active=True))

    # Custom key builder
    @cached(key_builder=lambda f, self, args, kw: f"user_data_{self.id}_{args[0]}")
    def get_data_by_type(self, data_type):
        return expensive_query(self.id, data_type)

    # Method with parameters (auto-includes in key)
    @cached("user_records:{id}", timeout=300, include_params=True)
    def get_records_by_date(self, start_date, end_date):
        return self.records.filter(date__range=[start_date, end_date])


# ============================================================================
# EXAMPLE 2: Standalone Functions
# ============================================================================

# Auto-generated key from function name + parameters
@cached(timeout=600)
def get_active_patients(clinic_id):
    return Patient.objects.filter(clinic_id=clinic_id, is_active=True)

# Custom key template
@cached("clinic_revenue:{clinic_id}", timeout=1800)
def calculate_clinic_revenue(clinic_id, start_date, end_date):
    # clinic_id in key, dates hashed
    return Invoice.objects.filter(...).aggregate(Sum('amount'))

# Lambda key builder
@cached(
    key=lambda clinic_id, status: f"patients_{clinic_id}_{status}",
    timeout=300
)
def get_patients_by_status(clinic_id, status):
    return Patient.objects.filter(clinic_id=clinic_id, status=status)


# ============================================================================
# EXAMPLE 3: Serializer Methods
# ============================================================================

from rest_framework import serializers

class PatientSerializer(serializers.ModelSerializer):
    medical_summary = serializers.SerializerMethodField()
    recent_vitals = serializers.SerializerMethodField()

    # Access instance via template
    @cached("patient_summary:{instance.id}", timeout=600)
    def get_medical_summary(self, instance):
        return calculate_summary(instance)

    # Lambda with full control
    @cached(
        key=lambda self, obj: f"vitals_{obj.id}_{obj.updated_at.timestamp()}",
        timeout=180
    )
    def get_recent_vitals(self, instance):
        return instance.vital_signs.latest()


# ============================================================================
# EXAMPLE 4: View Methods
# ============================================================================

from rest_framework import viewsets

class PatientViewSet(viewsets.ModelViewSet):

    # Access request in key template
    @cached("patient_list:{request.user.id}", timeout=600)
    def list(self, request):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    # Custom key builder with request context
    @cached(
        key_builder=lambda f, self, args, kw:
            f"patient_{kw.get('pk')}_{args[0].user.id}",
        timeout=300
    )
    def retrieve(self, request, pk=None):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    # Auto-generated (function name + params)
    @cached(timeout=900)
    def get_queryset(self):
        return Patient.objects.filter(clinic=self.request.user.clinic)


# ============================================================================
# EXAMPLE 5: Class Methods and Static Methods
# ============================================================================

class Patient(models.Model):

    @classmethod
    @cached("patient_statistics", timeout=1800)
    def get_statistics(cls):
        return {
            'total': cls.objects.count(),
            'active': cls.objects.filter(is_active=True).count(),
        }

    @staticmethod
    @cached("risk_calculation", timeout=3600)
    def calculate_risk_score(age, conditions, medications):
        return complex_calculation(age, conditions, medications)


# ============================================================================
# EXAMPLE 6: Namespaced Caching
# ============================================================================

class Clinic(models.Model):

    # Group related caches with namespace
    @cached("stats:{id}", namespace="clinic", timeout=600)
    def get_statistics(self):
        # Cache key: tenant:schema:clinic:stats:123
        return calculate_stats(self)

    @cached("revenue:{id}", namespace="clinic", timeout=1800)
    def get_revenue(self):
        # Cache key: tenant:schema:clinic:revenue:123
        return calculate_revenue(self)


# ============================================================================
# EXAMPLE 7: Manual Invalidation
# ============================================================================

# Every cached function has an invalidate() method
user = User.objects.get(id=123)

# Invalidate specific cache
user.get_all_permissions.invalidate(user)

# For functions
get_active_patients.invalidate(clinic_id=456)

# Or use the generic invalidate_cache helper:
from dynamic_cache import invalidate_cache

invalidate_cache("user_perms:{id}", user_id=123)
invalidate_cache("patient_list:{user_id}", user_id=456)


# ============================================================================
# EXAMPLE 8: Non-Tenant Aware Caching (Global)
# ============================================================================

@cached("global_config", tenant_aware=False, timeout=3600)
def get_global_config():
    # Cache key: global_config (no tenant prefix)
    return SystemConfig.objects.all()


# ============================================================================
# EXAMPLE 9: Disable Parameter Inclusion
# ============================================================================

@cached("daily_report", include_params=False, timeout=86400)
def generate_daily_report(date):
    # Cache key: tenant:schema:daily_report
    # Same cache for all dates (only refreshes once per day)
    return create_report(date)
"""
