from rest_framework import serializers
from .models import TutorProfile, Resume, ParentReview, Group, Student


class TutorProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = TutorProfile
        fields = "__all__"


class ResumeSerializer(serializers.ModelSerializer):
    student_crm_id = serializers.SlugRelatedField(
        slug_field="student_crm_id",
        queryset=Student.objects.all(),
        source="student"
    )

    class Meta:
        model = Resume
        fields = ("id", "student_crm_id", "content", "is_verified", "created_at", "updated_at")


class ParentReviewSerializer(serializers.ModelSerializer):
    student_crm_id = serializers.SlugRelatedField(
        slug_field="student_crm_id",
        queryset=Student.objects.all(),
        source="student"
    )

    class Meta:
        model = ParentReview
        fields = ("id", "student_crm_id", "content", "created_at", "updated_at")


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = "__all__"


class StudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = "__all__"


class TutorRegisterRequestSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=20)
    tutor_branch_id = serializers.CharField(max_length=255)

    def validate_phone_number(self, value):
        # Remove all non-digit characters from phone number
        cleaned_phone = "".join(filter(str.isdigit, value))
        if len(cleaned_phone) < 10:  # Minimum length check
            raise serializers.ValidationError("Phone number must contain at least 10 digits")
        return cleaned_phone


class TutorLoginSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=20)

    def validate_phone_number(self, value):
        # Remove all non-digit characters from phone number
        cleaned_phone = "".join(filter(str.isdigit, value))
        if len(cleaned_phone) < 10:  # Minimum length check
            raise serializers.ValidationError("Phone number must contain at least 10 digits")
        return cleaned_phone


class ResumeUpdateSerializer(serializers.Serializer):
    content = serializers.CharField(required=False)


class ResumeCreateSerializer(serializers.Serializer):
    student_crm_id = serializers.CharField(max_length=255)
    content = serializers.CharField()


class TokenSerializer(serializers.Serializer):
    access_token = serializers.CharField()
    token_type = serializers.CharField()
