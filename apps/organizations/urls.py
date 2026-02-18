from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import OrganizationRegisterView
from .revenue_views import RevenueViewSet

router = DefaultRouter()

router.register(r'revenue', RevenueViewSet, basename='revenue')

urlpatterns = [
    path('register/', OrganizationRegisterView.as_view(), name='register'),
    path('', include(router.urls))
]
