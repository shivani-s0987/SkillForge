from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async

class AdminStudentAnalyticsConsumer(AsyncJsonWebsocketConsumer):
    """WebSocket consumer that streams real-time analytics updates for a student to admin clients."""

    async def connect(self):
        self.student_id = self.scope['url_route']['kwargs']['student_id']
        self.group_name = f"admin_student_{self.student_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        # Admin client shouldn't need to send data; ignore or use for pings
        pass

    async def analytics_update(self, event):
        # event is expected to contain 'data' key with latest analytics
        data = event.get('data')
        await self.send_json({
            'type': 'analytics.update',
            'data': data
        })
