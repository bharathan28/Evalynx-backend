"""
Authentication service layer.

All business logic is isolated here. Views are thin orchestrators.
"""

from __future__ import annotations

from rest_framework_simplejwt.tokens import RefreshToken

from .models import User


class AuthService:
    @staticmethod
    def register(validated_data: dict) -> dict:
        """
        Create a new user and immediately return a JWT token pair so the
        user is logged in after registration without a second round-trip.
        """
        user = User.objects.create_user(**validated_data)
        tokens = AuthService._issue_tokens(user)
        return {
            "user": {
                "id": str(user.id),
                "name": user.name,
                "email": user.email,
                "created_at": user.created_at.isoformat(),
            },
            **tokens,
        }

    @staticmethod
    def logout(refresh_token: str) -> None:
        """
        Blacklist the provided refresh token, invalidating the session.
        The access token will expire naturally (short-lived by design).
        """
        token = RefreshToken(refresh_token)
        token.blacklist()

    @staticmethod
    def _issue_tokens(user: User) -> dict:
        refresh = RefreshToken.for_user(user)
        return {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        }
