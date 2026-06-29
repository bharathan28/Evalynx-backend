from rest_framework import status
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.analytics.serializers import ResultSerializer
from apps.analytics.services import AnalyticsService

from .serializers import (
    AnswerSerializer,
    InterviewDetailSerializer,
    InterviewSummarySerializer,
    QuestionSerializer,
    StartInterviewSerializer,
    SubmitAnswerSerializer,
)
from .services import InterviewService


class StartInterviewView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        serializer = StartInterviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            interview, questions = InterviewService.start_interview(
                user=request.user,
                **serializer.validated_data,
            )
        except Exception as exc:
            return Response(
                {"success": False, "error": {"message": str(exc)}},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {
                "success": True,
                "data": {
                    "interview": InterviewSummarySerializer(interview).data,
                    "questions": QuestionSerializer(questions, many=True).data,
                },
            },
            status=status.HTTP_201_CREATED,
        )


class GetQuestionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        interview_id = request.query_params.get("interview_id")
        question_number = request.query_params.get("number")

        if not interview_id or not question_number:
            return Response(
                {"success": False, "error": {"message": "interview_id and number are required."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            question = InterviewService.get_question(
                interview_id=interview_id,
                question_number=int(question_number),
                user=request.user,
            )
        except ValueError as exc:
            return Response(
                {"success": False, "error": {"message": str(exc)}},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response({"success": True, "data": QuestionSerializer(question).data})


class SubmitAnswerView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, JSONParser]

    def post(self, request: Request) -> Response:
        data = {**request.data}
        if "video" in request.FILES:
            data["video"] = request.FILES["video"]

        serializer = SubmitAnswerSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        vd = serializer.validated_data

        try:
            answer = InterviewService.submit_answer(
                interview_id=vd["interview_id"],
                question_number=vd["question_number"],
                user=request.user,
                video_file=vd.get("video"),
                transcript_override=vd.get("transcript_override", ""),
            )
        except ValueError as exc:
            return Response(
                {"success": False, "error": {"message": str(exc)}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            return Response(
                {"success": False, "error": {"message": "Processing failed.", "detail": str(exc)}},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {"success": True, "data": AnswerSerializer(answer).data},
            status=status.HTTP_200_OK,
        )


class CancelInterviewView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        interview_id = request.data.get("interview_id")
        if not interview_id:
            return Response(
                {"success": False, "error": {"message": "interview_id is required."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            interview = InterviewService.cancel_interview(
                interview_id=interview_id, user=request.user
            )
        except ValueError as exc:
            return Response(
                {"success": False, "error": {"message": str(exc)}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"success": True, "data": InterviewSummarySerializer(interview).data}
        )


class InterviewResultView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        interview_id = request.query_params.get("interview_id")
        if not interview_id:
            return Response(
                {"success": False, "error": {"message": "interview_id is required."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = AnalyticsService.get_or_generate_result(
                interview_id=interview_id, user=request.user
            )
        except ValueError as exc:
            return Response(
                {"success": False, "error": {"message": str(exc)}},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response({"success": True, "data": ResultSerializer(result).data})


class InterviewHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        interviews = InterviewService.get_history(request.user)
        return Response(
            {
                "success": True,
                "data": InterviewSummarySerializer(interviews, many=True).data,
            }
        )


class InterviewDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, interview_id: str) -> Response:
        try:
            from .models import Interview
            interview = Interview.objects.get(id=interview_id, user=request.user)
        except Exception:
            return Response(
                {"success": False, "error": {"message": "Interview not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            {"success": True, "data": InterviewDetailSerializer(interview).data}
        )
