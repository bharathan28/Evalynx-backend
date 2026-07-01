from django.urls import path

from .views import (
    CancelInterviewView,
    GetQuestionView,
    InterviewDetailView,
    InterviewHistoryView,
    InterviewResultView,
    SkipQuestionView,
    StartInterviewView,
    SubmitAnswerView,
)

urlpatterns = [
    # Literal routes MUST come before the <uuid:interview_id>/ catch-all
    path("start/", StartInterviewView.as_view(), name="interview-start"),
    path("question/", GetQuestionView.as_view(), name="interview-question"),
    path("submit-answer/", SubmitAnswerView.as_view(), name="interview-submit-answer"),
    path("skip/", SkipQuestionView.as_view(), name="interview-skip"),
    path("cancel/", CancelInterviewView.as_view(), name="interview-cancel"),
    path("result/", InterviewResultView.as_view(), name="interview-result"),
    path("<uuid:interview_id>/", InterviewDetailView.as_view(), name="interview-detail"),
]
