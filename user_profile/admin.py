from django.contrib import admin
from .models import Tutor, Experience, Education, Skill


# ------------------------------
# Tutor Admin
# ------------------------------
@admin.register(Tutor)
class TutorAdmin(admin.ModelAdmin):
    list_display = ("id", "display_name", "user", "headline", "status")
    list_filter = ("status",)
    search_fields = ("display_name", "headline", "user__email", "user__username")
    actions = ["mark_verified", "mark_rejected"]

    def mark_verified(self, request, queryset):
        updated = queryset.update(status=Tutor.VERIFIED)
        self.message_user(request, f"{updated} tutor(s) marked as Verified.")

    def mark_rejected(self, request, queryset):
        updated = queryset.update(status=Tutor.REJECTED)
        self.message_user(request, f"{updated} tutor(s) marked as Rejected.")

    mark_verified.short_description = "Mark selected tutors as Verified"
    mark_rejected.short_description = "Mark selected tutors as Rejected"


# ------------------------------
# Experience Admin
# ------------------------------
@admin.register(Experience)
class ExperienceAdmin(admin.ModelAdmin):
    list_display = ("tutor", "company_name", "position", "start_date", "end_date")
    search_fields = ("company_name", "position", "tutor__display_name")


# ------------------------------
# Education Admin
# ------------------------------
@admin.register(Education)
class EducationAdmin(admin.ModelAdmin):
    list_display = ("tutor", "highest_qualification", "name_of_institution", "year_of_qualification")
    search_fields = ("highest_qualification", "name_of_institution", "tutor__display_name")


# ------------------------------
# Skill Admin
# ------------------------------
@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ("tutor", "skill_name")
    search_fields = ("skill_name", "tutor__display_name")
