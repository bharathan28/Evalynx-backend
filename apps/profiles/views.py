from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import ProfileSerializer, ResumeUploadSerializer
from .services import ProfileService


class ResumeUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

    def post(self, request: Request) -> Response:
        serializer = ResumeUploadSerializer(data=request.FILES)
        serializer.is_valid(raise_exception=True)

        try:
            profile = ProfileService.process_resume(
                user=request.user,
                file=serializer.validated_data["resume"],
            )
        except ValueError as exc:
            return Response(
                {"success": False, "error": {"message": str(exc)}},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        except Exception as exc:
            return Response(
                {
                    "success": False,
                    "error": {
                        "message": "Resume processing failed. Please try again.",
                        "detail": str(exc),
                    },
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {
                "success": True,
                "data": ProfileSerializer(profile).data,
                "message": "Resume processed successfully.",
            },
            status=status.HTTP_200_OK,
        )


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        profile = ProfileService.get_or_create_profile(request.user)
        return Response(
            {"success": True, "data": ProfileSerializer(profile).data}
        )
