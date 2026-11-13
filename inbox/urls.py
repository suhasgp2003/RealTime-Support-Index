from django.urls import path
from . import views

urlpatterns = [
    path("conversations/<int:conversation_id>/", views.conversation_page),
    path("api/conversations/<int:conversation_id>/messages/", views.MessageListCreate.as_view()),
]