from django.urls import path
from .views import OrganizationRegisterView

urlpatterns = [
    path('register/', OrganizationRegisterView.as_view(), name='register'),
]
