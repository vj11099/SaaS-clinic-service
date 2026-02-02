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
    path('check-status/', OrganizationSubscriptionViewSet.as_view(
        {'post': 'check_status'}), name='check-status'),
]

urlpatterns = [
    path('', include(router.urls)),
    path('subscription/', include(subscription_patterns)),
]

"""
Add to your main urls.py:

from django.urls import path, include

urlpatterns = [
    ...
    path('api/subscriptions/', include('subscriptions.urls')),
]

This will create the following endpoints:

GET    /api/subscriptions/plans/                  - List all plans
GET    /api/subscriptions/plans/{id}/              - Get plan by ID
GET    /api/subscriptions/plans/{slug}/            - Get plan by slug
GET    /api/subscriptions/subscription/current/    - Get current subscription
POST   /api/subscriptions/subscription/subscribe/  - Subscribe to a plan
POST   /api/subscriptions/subscription/renew/      - Renew subscription
POST   /api/subscriptions/subscription/cancel/     - Cancel subscription
GET    /api/subscriptions/subscription/history/    - Get subscription history
POST   /api/subscriptions/subscription/check-status/ - Check subscription status
"""
