from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction

from .serializers import MessageSerializer


def broadcast_message(message):
    payload = dict(MessageSerializer(message).data)
    group = f"conversation_{message.conversation_id}"
    transaction.on_commit(
        lambda: async_to_sync(get_channel_layer().group_send)(
            group, {"type": "chat.message", "message": payload}
        )
    )

def broadcast_assignment(conversation):
    group = f"conversation_{conversation.id}"
    username = conversation.assigned_to.get_username() if conversation.assigned_to else None
    transaction.on_commit(
        lambda: async_to_sync(get_channel_layer().group_send)(
            group, {"type": "conversation.assigned", "assigned_to": username}
        )
    )    