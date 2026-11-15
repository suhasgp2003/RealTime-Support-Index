import hmac

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, render
from rest_framework import generics, serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Conversation, Message
from .serializers import MessageSerializer
from .services import broadcast_assignment, broadcast_message


@login_required
def conversation_page(request, conversation_id):
    conversation = get_object_or_404(
        Conversation.objects.select_related("assigned_to"), pk=conversation_id
    )
    owner = conversation.assigned_to.get_username() if conversation.assigned_to else "nobody"
    return render(
        request,
        "inbox/conversation.html",
        {"conversation_id": conversation_id, "owner": owner},
    )


class MessageListCreate(generics.ListCreateAPIView):
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Message.objects.filter(conversation_id=self.kwargs["conversation_id"])

    def perform_create(self, serializer):
        conversation = get_object_or_404(Conversation, pk=self.kwargs["conversation_id"])
        message = serializer.save(
            conversation=conversation, sender_type=Message.Sender.AGENT
        )
        broadcast_message(message)


class AssignConversation(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, conversation_id):
        get_object_or_404(Conversation, pk=conversation_id)

        # one atomic UPDATE: succeeds only if nobody owns it yet
        claimed = Conversation.objects.filter(
            pk=conversation_id, assigned_to__isnull=True
        ).update(assigned_to=request.user)

        conversation = Conversation.objects.select_related("assigned_to").get(pk=conversation_id)

        if not claimed and conversation.assigned_to_id != request.user.id:
            return Response(
                {"detail": f"Already assigned to {conversation.assigned_to.get_username()}"},
                status=409,
            )
        if claimed:
            broadcast_assignment(conversation)
        return Response({"assigned_to": conversation.assigned_to.get_username()})


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