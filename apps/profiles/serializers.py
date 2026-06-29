from rest_framework import serializers

from .models import Profile


class ProfileSerializer(serializers.ModelSerializer):
    """Full profile representation returned to the client."""

    is_complete = serializers.BooleanField(read_only=True)

    class Meta:
        model = Profile
        fields = (
            "id",
            "full_name",
            "education",
            "skills",
            "experience",
            "projects",
            "certifications",
            "resume_parsed_at",
            "is_complete",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class ResumeUploadSerializer(serializers.Serializer):
    """Validates the incoming resume file."""

    resume = serializers.FileField()

    def validate_resume(self, file):
        # Accept only PDFs
        if not file.name.lower().endswith(".pdf"):
            raise serializers.ValidationError("Only PDF files are accepted.")
        # 10 MB size limit
        if file.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("File size must not exceed 10 MB.")
        return file
