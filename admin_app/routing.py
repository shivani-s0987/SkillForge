from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'^ws/admin/student_analytics/(?P<student_id>[^/]+)/$', consumers.AdminStudentAnalyticsConsumer.as_asgi()),
]
