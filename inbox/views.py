from django.shortcuts import render


def conversation_page(request, conversation_id):
    return render(request, "inbox/conversation.html", {"conversation_id": conversation_id})