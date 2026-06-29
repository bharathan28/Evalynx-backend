from django.urls import path

from .views import ProfileView, ResumeUploadView

urlpatterns = [
    path("resume/upload/", ResumeUploadView.as_view(), name="resume-upload"),
    path("profile/", ProfileView.as_view(), name="profile-detail"),
]
