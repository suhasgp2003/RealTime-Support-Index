from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.shortcuts import get_object_or_404, render
from rest_framework import generics

from .models import Conversation, Message
from .serializers import MessageSerializer


def conversation_page(request, conversation_id):
    return render(request, "inbox/conversation.html", {"conversation_id": conversation_id})


class MessageListCreate(generics.ListCreateAPIView):
    serializer_class = MessageSerializer
    authentication_classes = []   # TEMPORARY: step 7 adds real auth
    permission_classes = []       # TEMPORARY

    def get_queryset(self):
        return Message.objects.filter(conversation_id=self.kwargs["conversation_id"])

    def perform_create(self, serializer):
        conversation = get_object_or_404(Conversation, pk=self.kwargs["conversation_id"])
        message = serializer.save(conversation=conversation)
        payload = dict(MessageSerializer(message).data)
        group = f"conversation_{conversation.id}"
        transaction.on_commit(
            lambda: async_to_sync(get_channel_layer().group_send)(
                group, {"type": "chat.message", "message": payload}
            )
        )