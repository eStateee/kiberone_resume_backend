from django.contrib import admin
from .models import TutorProfile, Resume, ParentReview, Group, Student


class TutorProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "tutor_name", "tutor_crm_id", "branch", "is_senior", "phone_number")
    list_filter = ("branch", "is_senior")
    search_fields = ("tutor_name", "tutor_crm_id", "phone_number")
    ordering = ("tutor_name",)


class ResumeAdmin(admin.ModelAdmin):
    list_display = ("id", "get_student_crm_id", "get_student_name", "is_verified", "created_at", "updated_at")
    list_filter = ("is_verified", "created_at")
    search_fields = ("student__student_crm_id", "student__student_name", "id")
    ordering = ("-created_at",)

    def get_student_crm_id(self, obj):
        return obj.student.student_crm_id
    get_student_crm_id.short_description = "Student CRM ID"
    get_student_crm_id.admin_order_field = "student__student_crm_id"

    def get_student_name(self, obj):
        return obj.student.student_name
    get_student_name.short_description = "Student Name"
    get_student_name.admin_order_field = "student__student_name"


class ParentReviewAdmin(admin.ModelAdmin):
    list_display = ("id", "get_student_crm_id", "get_student_name", "created_at", "updated_at")
    list_filter = ("created_at",)
    search_fields = ("student__student_crm_id", "student__student_name")
    ordering = ("-created_at",)

    def get_student_crm_id(self, obj):
        return obj.student.student_crm_id
    get_student_crm_id.short_description = "Student CRM ID"
    get_student_crm_id.admin_order_field = "student__student_crm_id"

    def get_student_name(self, obj):
        return obj.student.student_name
    get_student_name.short_description = "Student Name"
    get_student_name.admin_order_field = "student__student_name"


class GroupAdmin(admin.ModelAdmin):
    list_display = ("id", "crm_group_id", "name", "level_id", "status_id")
    list_filter = ("level_id", "status_id")
    search_fields = ("name", "crm_group_id")
    ordering = ("name",)


class StudentAdmin(admin.ModelAdmin):
    list_display = ("id", "student_crm_id", "student_name", "group", "study_start_date")
    list_filter = ("group",)
    search_fields = ("student_name", "student_crm_id")
    ordering = ("student_name",)


# Register your models here.
admin.site.register(TutorProfile, TutorProfileAdmin)
admin.site.register(Resume, ResumeAdmin)
admin.site.register(ParentReview, ParentReviewAdmin)
admin.site.register(Group, GroupAdmin)
admin.site.register(Student, StudentAdmin)
