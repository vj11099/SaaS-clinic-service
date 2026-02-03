from django.urls import path
from .views import LoginView, RegisterUserView, VerifyUserView
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path('register/', RegisterUserView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('verify/', VerifyUserView.as_view(), name='verify_password'),
]
