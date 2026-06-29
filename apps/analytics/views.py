from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import ResultSummarySerializer
from .services import AnalyticsService


class HistoryView(APIView):
    """Returns a paginated list of all past interview results for the user."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        results = AnalyticsService.get_user_history(request.user)
        return Response(
            {
                "success": True,
                "data": ResultSummarySerializer(results, many=True).data,
            }
        )
