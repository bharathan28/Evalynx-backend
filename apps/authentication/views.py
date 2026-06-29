"""
Authentication views.

Views are intentionally thin: they validate input, call the service layer,
and return a formatted response. Zero business logic lives here.
"""

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .serializers import CustomTokenObtainPairSerializer, RegisterSerializer, UserDetailSerializer
from .services import AuthService


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Service handles creation + token issuance
        payload = AuthService.register(serializer.validated_data)

        return Response(
            {"success": True, "data": payload},
            status=status.HTTP_201_CREATED,
        )


class LoginView(TokenObtainPairView):
    """Thin wrapper around simplejwt's token view with custom serializer."""

    permission_classes = [AllowAny]
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request: Request, *args, **kwargs) -> Response:
        response = super().post(request, *args, **kwargs)
        return Response(
            {"success": True, "data": response.data},
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"success": False, "error": {"message": "Refresh token is required."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            AuthService.logout(refresh_token)
        except Exception:
            return Response(
                {"success": False, "error": {"message": "Invalid or expired token."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"success": True, "data": {"message": "Logged out successfully."}})


class MeView(APIView):
    """Return the currently authenticated user's profile."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        serializer = UserDetailSerializer(request.user)
        return Response({"success": True, "data": serializer.data})


class TokenRefreshViewCustom(TokenRefreshView):
    """Wraps simplejwt refresh view in the standard response envelope."""

    def post(self, request: Request, *args, **kwargs) -> Response:
        response = super().post(request, *args, **kwargs)
        return Response({"success": True, "data": response.data})
