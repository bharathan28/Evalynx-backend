"""Custom manager for the User model with email-based authentication."""

from django.contrib.auth.models import BaseUserManager


class UserManager(BaseUserManager):
    """Manager that uses email as the unique identifier instead of username."""

    def create_user(self, email: str, name: str, password: str, **extra_fields):
        if not email:
            raise ValueError("Email address is required.")
        if not name:
            raise ValueError("Full name is required.")

        email = self.normalize_email(email)
        user = self.model(email=email, name=name, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, name: str, password: str, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if not extra_fields.get("is_staff"):
            raise ValueError("Superuser must have is_staff=True.")
        if not extra_fields.get("is_superuser"):
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, name, password, **extra_fields)
