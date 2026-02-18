from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import APIKeyViewSet

router = DefaultRouter()
router.register(r'api-keys', APIKeyViewSet, basename='apikey')

urlpatterns = [
    path('', include(router.urls)),
]
