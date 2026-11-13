import hmac

from django.conf import settings
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, render
from rest_framework import generics, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Conversation, Message
from .serializers import MessageSerializer
from .services import broadcast_message


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
        broadcast_message(message)


class InboundSerializer(serializers.Serializer):
    external_id = serializers.CharField(max_length=200)
    customer_name = serializers.CharField(max_length=120)
    customer_email = serializers.EmailField()
    body = serializers.CharField()


class InboundWebhook(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        secret = request.headers.get("X-Webhook-Secret", "")
        if not settings.INGEST_SECRET or not hmac.compare_digest(
            secret.encode(), settings.INGEST_SECRET.encode()
        ):
            return Response({"detail": "unauthorized"}, status=401)

        serializer = InboundSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            with transaction.atomic():
                conversation = (
                    Conversation.objects.filter(
                        customer_email=data["customer_email"],
                        status=Conversation.Status.OPEN,
                    )
                    .order_by("-created_at")
                    .first()
                )
                if conversation is None:
                    conversation = Conversation.objects.create(
                        customer_name=data["customer_name"],
                        customer_email=data["customer_email"],
                    )
                message = Message.objects.create(
                    conversation=conversation,
                    sender_type=Message.Sender.CUSTOMER,
                    body=data["body"],
                    external_id=data["external_id"],
                )
                broadcast_message(message)
        except IntegrityError:
            return Response({"duplicate": True}, status=200)

        return Response({"id": message.id, "conversation": conversation.id}, status=201)