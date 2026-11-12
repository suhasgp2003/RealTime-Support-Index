from channels.generic.websocket import AsyncJsonWebsocketConsumer


class ConversationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        self.group_name = f"conversation_{self.conversation_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content):
        # a browser sent us something: broadcast it to everyone in the group
        await self.channel_layer.group_send(
            self.group_name,
            {"type": "chat.message", "body": content.get("body", "")},
        )

    async def chat_message(self, event):
        # called for every group member when group_send fires
        await self.send_json({"body": event["body"]})