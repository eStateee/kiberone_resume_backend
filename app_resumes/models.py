from django.db import models


class TutorProfile(models.Model):
    id = models.AutoField(primary_key=True)
    tutor_crm_id = models.CharField(max_length=255, null=True, unique=True)
    tutor_name = models.CharField(max_length=255, null=True)
    branch = models.CharField(max_length=255, null=True)
    is_senior = models.BooleanField(default=False)
    phone_number = models.CharField(max_length=20, unique=True)

    # Additional models based on CRM response
    branch_ids = models.JSONField(null=True)  # Corresponds to "branch_ids" in the JSON
    dob = models.CharField(max_length=10, null=True, blank=True)  # Corresponds to "dob" in the JSON
    gender = models.IntegerField(null=True, blank=True)  # Corresponds to "gender" in the JSON
    streaming_id = models.IntegerField(null=True, blank=True)  # Corresponds to "streaming_id" in the JSON
    note = models.TextField(null=True, blank=True)  # Corresponds to "note" in the JSON
    e_date = models.CharField(max_length=10, null=True, blank=True)  # Corresponds to "e_date" in the JSON
    avatar_url = models.CharField(max_length=500, null=True, blank=True)  # Corresponds to "avatar_url" in the JSON
    phone = models.TextField(null=True, blank=True)  # Corresponds to "phone" array in the JSON, storing as a single string
    email = models.TextField(null=True, blank=True)  # Corresponds to "email" array in the JSON, storing as a single string
    web = models.TextField(null=True, blank=True)  # Corresponds to "web" array in the JSON, storing as a single string
    addr = models.TextField(null=True, blank=True)  # Corresponds to "addr" array in the JSON, storing as a single string
    teacher_to_skill = models.JSONField(null=True, blank=True)  # Corresponds to "teacher-to-skill" in the JSON

    def save(self, *args, **kwargs):
        # Process arrays from CRM response to single values before saving
        if isinstance(self.phone, list) and len(self.phone) > 0:
            self.phone = self.phone[0] if self.phone[0] else None
        if isinstance(self.email, list) and len(self.email) > 0:
            self.email = self.email[0] if self.email[0] else None
        if isinstance(self.web, list) and len(self.web) > 0:
            self.web = self.web[0] if self.web[0] else None
        if isinstance(self.addr, list) and len(self.addr) > 0:
            self.addr = self.addr[0] if self.addr[0] else None
        super().save(*args, **kwargs)

    def __str__(self):
        return self.tutor_name or f"Tutor {self.id}"

    class Meta:
        verbose_name = "Tutor Profile"
        verbose_name_plural = "Tutor Profiles"
        ordering = ["tutor_name"]


class Resume(models.Model):
    id = models.AutoField(primary_key=True)
    student_crm_id = models.CharField(max_length=255)
    content = models.TextField(null=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Process any array values to single values before saving
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Resume for student {self.student_crm_id}"

    class Meta:
        verbose_name = "Resume"
        verbose_name_plural = "Resumes"
        ordering = ["-created_at"]


class ParentReview(models.Model):
    id = models.AutoField(primary_key=True)
    student_crm_id = models.CharField(max_length=255)
    content = models.TextField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Process any array values to single values before saving
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Review for student {self.student_crm_id}"

    class Meta:
        verbose_name = "Parent Review"
        verbose_name_plural = "Parent Reviews"
        ordering = ["-created_at"]


class Group(models.Model):
    id = models.AutoField(primary_key=True)
    crm_group_id = models.IntegerField(unique=True)  # Corresponds to "id" in the JSON
    branch_ids = models.JSONField()  # Corresponds to "branch_ids" in the JSON
    teacher_ids = models.JSONField()  # Corresponds to "teacher_ids" in the JSON
    name = models.CharField(max_length=500)  # Corresponds to "name" in the JSON
    level_id = models.IntegerField()  # Corresponds to "level_id" in the JSON
    status_id = models.IntegerField()  # Corresponds to "status_id" in the JSON
    company_id = models.IntegerField(null=True)  # Corresponds to "company_id" in the JSON
    streaming_id = models.IntegerField(null=True)  # Corresponds to "streaming_id" in the JSON
    limit = models.IntegerField()  # Corresponds to "limit" in the JSON
    note = models.TextField(null=True)  # Corresponds to "note" in the JSON
    b_date = models.CharField(max_length=10, null=True)  # Corresponds to "b_date" in the JSON
    e_date = models.CharField(max_length=10, null=True)  # Corresponds to "e_date" in the JSON
    created_at = models.CharField(max_length=20, null=True)  # Corresponds to "created_at" in the JSON
    updated_at = models.CharField(max_length=20, null=True)  # Corresponds to "updated_at" in the JSON
    custom_aerodromnaya = models.CharField(max_length=10, null=True)  # Corresponds to "custom_aerodromnaya" in the JSON

    def save(self, *args, **kwargs):
        # Process arrays from CRM response to single values before saving
        if isinstance(self.branch_ids, list) and len(self.branch_ids) > 0:
            self.branch_ids = self.branch_ids[0] if self.branch_ids[0] else None
        if isinstance(self.teacher_ids, list) and len(self.teacher_ids) > 0:
            self.teacher_ids = self.teacher_ids[0] if self.teacher_ids[0] else None
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name or f"Group {self.id}"

    class Meta:
        verbose_name = "Group"
        verbose_name_plural = "Groups"
        ordering = ["name"]


class Student(models.Model):
    id = models.AutoField(primary_key=True)
    student_crm_id = models.IntegerField(unique=True)  # Corresponds to "customer_id" in the JSON
    student_name = models.CharField(max_length=255)  # Corresponds to "client_name" in the JSON
    group = models.ForeignKey("Group", related_name="students", null=True, on_delete=models.CASCADE)
    study_start_date = models.CharField(max_length=20, null=True, blank=True)  # Corresponds to "custom_datano" in CRM (format: "DD.MM.YYYY")

    def save(self, *args, **kwargs):
        # Process any array values to single values before saving
        super().save(*args, **kwargs)

    def __str__(self):
        return self.student_name or f"Student {self.id}"

    class Meta:
        verbose_name = "Student"
        verbose_name_plural = "Students"
        ordering = ["student_name"]
