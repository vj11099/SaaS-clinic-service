from django.conf import settings
from rest_framework_simplejwt.views import TokenObtainPairView
from ..serializers import (
    LoginSerializer, RegisterSerializer, UserSerializer,
    ResetPasswordSerializer, SubscriptionAwareTokenRefreshSerializer
)
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from apps.permissions import HasPermission
from rest_framework import (
    permissions, generics, status, viewsets, exceptions, views
)
from rest_framework.response import Response
from ..models import User
from ..permissions.users import IsVerifiedUser
from utils.registration_mail import send_verification_email
from django.db import connection
from django_tenants.utils import get_public_schema_name
from rest_framework_simplejwt.exceptions import TokenError


class RegisterUserView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [HasPermission]
    required_permission = 'users.create'

    def create(self, request, *args, **kwargs):
        """
        Overridden create method to enforce subscription limits
        before registering a new user.
        """

        tenant = connection.tenant

        # Check if we are in a valid tenant context (not public schema)
        if tenant.schema_name != get_public_schema_name():

            if not tenant.can_add_member():
                # Get details for error message
                plan = tenant.subscription_plan
                member_limit = tenant.get_member_limit()
                current_count = tenant.current_member_count

                # Build appropriate error message
                if not plan:
                    error_message = "No active subscription plan found."
                elif not tenant.is_subscription_active():
                    error_message = (
                        f"Your subscription has expired. "
                        f"Please renew to add more members."
                    )
                else:
                    error_message = (
                        f"Your current plan ({plan.name}) allows a maximum of "
                        f"{member_limit if member_limit != -1 else 'unlimited'} "
                        f"active members. You currently have {current_count}."
                    )

                return Response(
                    {
                        "error": "Cannot add member",
                        "message": error_message,
                        "current_count": current_count,
                        "limit": member_limit
                    },
                    status=status.HTTP_403_FORBIDDEN
                )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        tenant.current_member_count += 1
        tenant.save(update_fields=['current_member_count', 'updated_at'])

        send_verification_email(user, None)

        return Response({
            "message": "Registration successful! Please check below email",
            "email": user.email
        }, status=status.HTTP_201_CREATED)


class VerifyUserView(generics.UpdateAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = ResetPasswordSerializer

    def patch(self, request, *args, **kwargs):
        return Response({
            "message": "Method unavailable, please use PUT",
        }, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def update(self, request):
        try:
            serializer = self.get_serializer(data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)

            email = serializer.validated_data.get('email')
            new_password = serializer.validated_data.get('new_password')
            old_password = serializer.validated_data.get('old_password')

            # Get user by email from the request body
            user = User.objects.get(email=email)

            expiry_hours = getattr(
                settings, 'PASSWORD_RESET_TIMEOUT_IN_SECONDS', 24 * 60 * 60)

            if not user.check_password(old_password):
                return Response({
                    "message": "Incorrect password",
                }, status=status.HTTP_400_BAD_REQUEST)

            if not user.is_password_updated(expiry_hours):
                return Response({
                    "error": "You have already updated your password." +
                    "If you want to reset your password " +
                    "please use /reset-password",
                    "expired": True
                }, status=status.HTTP_400_BAD_REQUEST)

            if not user.is_password_valid(expiry_hours):
                return Response({
                    "error": "Password reset time has expired.",
                    "expired": True
                }, status=status.HTTP_400_BAD_REQUEST)

            if user.is_password_previously_used(new_password):
                return Response({
                    "error": "Password was previously used." +
                    "Choose a different password.",
                    "expired": True
                }, status=status.HTTP_400_BAD_REQUEST)

            user.update_password(new_password)
            user.verify_user()
            user.save()

            return Response({
                "message": "Password set successfully! " +
                "You can now login.",
                "verified": True
            }, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({
                "error": "User doesn't exist"
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                "error": str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def perform_create(self, serializer):
        raise exceptions.Http404()

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save()


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer
    permission_classes = [permissions.AllowAny]


class ResetPasswordView(generics.UpdateAPIView):
    permission_classes = [IsVerifiedUser]
    serializer_class = ResetPasswordSerializer

    def update(self, request):
        try:
            serializer = self.get_serializer(data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)

            email = serializer.validated_data.get('email')
            new_password = serializer.validated_data.get('new_password')
            old_password = serializer.validated_data.get('old_password')

            # Get user by email from the request body
            user = User.objects.get(email=email)

            if not user.check_password(old_password):
                return Response({
                    "message": "Incorrect password",
                }, status=status.HTTP_400_BAD_REQUEST)

            if user.is_password_previously_used(new_password):
                return Response({
                    "error": "Password was previously used." +
                    "Choose a different password.",
                    "expired": True
                }, status=status.HTTP_400_BAD_REQUEST)

            user.update_password(new_password)
            user.save()

            return Response({
                "message": "Password set successfully! " +
                "You can now login.",
                "verified": True
            }, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({
                "error": "User doesn't exist"
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                "error": str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class LogoutView(views.APIView):
    # This permission class requires a valid Access Token in the header
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")

        if not refresh_token:
            return Response(
                {"error": "Refresh token is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()

            return Response(
                {"message": "Logout successful"},
                status=status.HTTP_205_RESET_CONTENT
            )

        except TokenError:
            # TokenError handles expired or invalid tokens specifically
            return Response(
                {"error": "Token is invalid or expired"},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"error": "An error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class SubscriptionAwareTokenRefreshView(TokenRefreshView):
    """
    Drop-in replacement for simplejwt's TokenRefreshView.
    Points to our custom serializer — nothing else changes.
    """
    serializer_class = SubscriptionAwareTokenRefreshSerializer
