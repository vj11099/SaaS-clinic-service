from django.conf import settings
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.permissions import AllowAny
from .serializers import (
    LoginSerializer, RegisterSerializer, UserSerializer,
    ResetPasswordSerializer
)
from rest_framework import (
    permissions, generics, status, viewsets, exceptions
)
from rest_framework.response import Response
from .models import User
from .permissions import IsVerifiedUser
from utils.registration_mail import send_verification_email
from django.db import connection
from django_tenants.utils import get_public_schema_name


class RegisterUserView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        """
        Overridden create method to enforce subscription limits
        before registering a new user.
        """

        tenant = connection.tenant

        # 2. Check if we are in a valid tenant context (not public schema)
        if tenant.schema_name != get_public_schema_name():

            plan = getattr(tenant, 'subscription_plan', None)

            if plan:
                member_limit = getattr(plan, 'max_members', 1)

                current_active_count = User.objects.filter(
                    is_active=True).count()

                if current_active_count >= member_limit:
                    return Response(
                        {
                            "error": "Member limit reached",
                            "message": (
                                f"Your current plan ({plan.name}) allows a maximum of {
                                    member_limit} "
                                f"active members. You currently have {
                                    current_active_count}."
                            ),
                            "current_count": current_active_count,
                            "limit": member_limit
                        },
                        status=status.HTTP_403_FORBIDDEN
                    )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        send_verification_email(user, None)

        return Response({
            "message": "Registration successful! Please check below email",
            "email": user.email
        }, status=status.HTTP_201_CREATED)


class VerifyUserView(generics.UpdateAPIView):
    # allowed_methods = ['put']
    permission_classes = [permissions.AllowAny]
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
    permission_classes = (AllowAny,)


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
