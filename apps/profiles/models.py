"""
Profile model.

Stores AI-extracted structured data from the user's resume.
The original PDF is never persisted — only the extracted data lives here.
"""

import uuid

from django.db import models

from apps.authentication.models import User


class Profile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")

    # Extracted from resume via AI — stored as structured JSON
    full_name = models.CharField(max_length=255, blank=True)
    education = models.JSONField(default=list)
    skills = models.JSONField(default=list)
    experience = models.JSONField(default=list)
    projects = models.JSONField(default=list)
    certifications = models.JSONField(default=list)

    # Raw text extracted from PDF (kept for re-parsing without re-upload)
    raw_resume_text = models.TextField(blank=True)

    resume_parsed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "profiles"
        verbose_name = "Profile"

    def __str__(self) -> str:
        return f"Profile({self.user.email})"

    @property
    def is_complete(self) -> bool:
        """Returns True when at least basic resume fields have been populated."""
        return bool(self.skills or self.experience or self.education)
