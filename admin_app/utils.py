from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

def broadcast_student_analytics(student_id, data):
    """Broadcast analytics update to group 'admin_student_<id>'"""
    channel_layer = get_channel_layer()
    group_name = f"admin_student_{student_id}"
    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            'type': 'analytics_update',
            'data': data
        }
    )
