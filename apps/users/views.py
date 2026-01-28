from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.permissions import AllowAny
from .serializers import LoginSerializer, RegisterSerializer, UserSerializer
from rest_framework import permissions, generics, status, viewsets, exceptions
from rest_framework.response import Response
from .models import User


class RegisterUserView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return Response({
            "message": "Registration successful!" +
            "Please check your email to verify your account",
            "email": user.email
        }, status=status.HTTP_201_CREATED)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def perform_create(self, serializer):
        # Use register view to create users
        raise exceptions.Http404()

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save()


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer
    permission_classes = (AllowAny,)
