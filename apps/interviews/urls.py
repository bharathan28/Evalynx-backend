from django.urls import path

from .views import (
    CancelInterviewView,
    GetQuestionView,
    InterviewDetailView,
    InterviewHistoryView,
    InterviewResultView,
    StartInterviewView,
    SubmitAnswerView,
)

urlpatterns = [
    path("start/", StartInterviewView.as_view(), name="interview-start"),
    path("question/", GetQuestionView.as_view(), name="interview-question"),
    path("submit-answer/", SubmitAnswerView.as_view(), name="interview-submit-answer"),
    path("cancel/", CancelInterviewView.as_view(), name="interview-cancel"),
    path("result/", InterviewResultView.as_view(), name="interview-result"),
    path("<uuid:interview_id>/", InterviewDetailView.as_view(), name="interview-detail"),
]
