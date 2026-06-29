"""Serializers for authentication endpoints."""

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import User


class RegisterSerializer(serializers.ModelSerializer):
    """Validates and creates a new user account."""

    password = serializers.CharField(
        write_only=True,
        min_length=8,
        validators=[validate_password],
    )
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ("id", "name", "email", "password", "password_confirm", "created_at")
        read_only_fields = ("id", "created_at")

    def validate(self, attrs: dict) -> dict:
        if attrs["password"] != attrs.pop("password_confirm"):
            raise serializers.ValidationError(
                {"password_confirm": "Passwords do not match."}
            )
        return attrs

    def create(self, validated_data: dict) -> User:
        return User.objects.create_user(**validated_data)


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Extends the default JWT serializer to embed user data in the response."""

    @classmethod
    def get_token(cls, user: User):
        token = super().get_token(user)
        # Embed lightweight claims — avoids extra round-trips on the frontend
        token["name"] = user.name
        token["email"] = user.email
        return token

    def validate(self, attrs: dict) -> dict:
        data = super().validate(attrs)
        # Attach user details alongside token pair
        data["user"] = UserDetailSerializer(self.user).data
        return data


class UserDetailSerializer(serializers.ModelSerializer):
    """Read-only representation of the authenticated user."""

    class Meta:
        model = User
        fields = ("id", "name", "email", "created_at")
        read_only_fields = fields
