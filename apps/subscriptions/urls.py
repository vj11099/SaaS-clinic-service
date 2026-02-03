"""
Subscription URLs
subscriptions/urls.py
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SubscriptionPlanViewSet, OrganizationSubscriptionViewSet

app_name = 'subscriptions'

router = DefaultRouter()
router.register(r'plans', SubscriptionPlanViewSet, basename='plans')

# Custom URL patterns for organization subscription management
subscription_patterns = [
    path('current/',
         OrganizationSubscriptionViewSet.as_view({'get': 'current'}), name='current'),
    path('subscribe/', OrganizationSubscriptionViewSet.as_view(
        {'post': 'subscribe'}), name='subscribe'),
    path('renew/',
         OrganizationSubscriptionViewSet.as_view({'post': 'renew'}), name='renew'),
    path('cancel/',
         OrganizationSubscriptionViewSet.as_view({'post': 'cancel'}), name='cancel'),
    path('history/',
         OrganizationSubscriptionViewSet.as_view({'get': 'history'}), name='history'),
]

urlpatterns = [
    path('', include(router.urls)),
    path('subscription/', include(subscription_patterns)),
]
