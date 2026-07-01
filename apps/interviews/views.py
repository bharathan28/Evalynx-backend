import logging

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

logger = logging.getLogger(__name__)


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
            logger.exception("Failed to start interview: %s", exc)
            return Response(
                {"success": False, "error": {"message": "Could not start interview. Please try again."}},
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
    """
    Fetch a single question by number.

    Works for ACTIVE, COMPLETED, and CANCELLED interviews — viewing a
    question is always read-only-safe, even after the interview ends.
    """

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
        except (ValueError, TypeError) as exc:
            return Response(
                {"success": False, "error": {"message": str(exc)}},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response({"success": True, "data": QuestionSerializer(question).data})


def _interview_progress_payload(answer, interview) -> dict:
    """
    Shared response shape for submit-answer and skip — tells the frontend
    exactly what to do next without it having to guess or make another
    (potentially failing) request.
    """
    is_last = interview.completed_questions >= interview.question_count
    return {
        "answer": AnswerSerializer(answer).data,
        "interview_status": interview.status,
        "completed_questions": interview.completed_questions,
        "question_count": interview.question_count,
        "is_complete": interview.status == "completed",
        "is_last_question": is_last,
        "next_question_number": None if is_last else interview.completed_questions + 1,
    }


class SubmitAnswerView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, JSONParser]

    def post(self, request: Request) -> Response:
        serializer = SubmitAnswerSerializer(
            data={
                "interview_id": request.data.get("interview_id"),
                "question_number": request.data.get("question_number"),
                "video": request.FILES.get("video"),
                "transcript_override": request.data.get("transcript_override", ""),
            }
        )
        serializer.is_valid(raise_exception=True)
        vd = serializer.validated_data

        try:
            answer, interview = InterviewService.submit_answer(
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
            logger.exception("Submit answer failed: %s", exc)
            return Response(
                {
                    "success": False,
                    "error": {
                        "message": "We couldn't process that answer. Please try again.",
                        "detail": str(exc),
                    },
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {"success": True, "data": _interview_progress_payload(answer, interview)},
            status=status.HTTP_200_OK,
        )


class SkipQuestionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        interview_id = request.data.get("interview_id")
        question_number = request.data.get("question_number")

        if not interview_id or question_number is None:
            return Response(
                {"success": False, "error": {"message": "interview_id and question_number are required."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            answer, interview = InterviewService.skip_question(
                interview_id=interview_id,
                question_number=int(question_number),
                user=request.user,
            )
        except (ValueError, TypeError) as exc:
            return Response(
                {"success": False, "error": {"message": str(exc)}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"success": True, "data": _interview_progress_payload(answer, interview)}
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
        from .models import Interview
        try:
            interview = Interview.objects.get(id=interview_id, user=request.user)
        except Interview.DoesNotExist:
            return Response(
                {"success": False, "error": {"message": "Interview not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            {"success": True, "data": InterviewDetailSerializer(interview).data}
        )
