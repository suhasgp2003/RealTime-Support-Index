from django.urls import path
from . import views

urlpatterns = [
    path("conversations/<int:conversation_id>/", views.conversation_page),
]