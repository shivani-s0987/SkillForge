from django.contrib import admin
from .models import Contest, EmailLog


@admin.register(Contest)
class ContestAdmin(admin.ModelAdmin):
	list_display = ('id', 'name', 'tutor', 'status', 'start_time', 'end_time', 'auto_email_results')
	list_filter = ('status', 'auto_email_results')
	search_fields = ('name',)


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
	list_display = ('id', 'to_email', 'contest', 'success', 'sent_at')
	list_filter = ('success', 'sent_at')
	search_fields = ('to_email', 'contest__name')
