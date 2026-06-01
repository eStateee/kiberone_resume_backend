from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch
from .models import TutorProfile, Resume, ParentReview, Group, Student
from .serializers import ResumeSerializer, ParentReviewSerializer


def mock_get_tutor_data_from_crm(phone_number, branch_id):
    cleaned_phone = "".join(filter(str.isdigit, str(phone_number)))
    return {
        "id": 123,
        "name": "Test Tutor",
        "branch_ids": [int(branch_id)] if branch_id else [1],
        "dob": "1990-01-01",
        "gender": 1,
        "streaming_id": 10,
        "note": "Some note",
        "e_date": "2026-12-31",
        "avatar_url": "http://img",
        "phone": [cleaned_phone],
        "email": ["tutor@example.com"],
        "web": [],
        "addr": [],
        "teacher-to-skill": [],
    }



class RegisterTutorViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.register_url = reverse("tutor-register")
        self.tutor_patcher = patch("app_resumes.views.get_tutor_data_from_crm", side_effect=mock_get_tutor_data_from_crm)
        self.mock_get_tutor = self.tutor_patcher.start()

    def tearDown(self):
        self.tutor_patcher.stop()


    def test_register_tutor_success(self):
        """
        Тест успешной регистрации преподавателя
        """
        data = {"phone_number": "375 44 712 3218", "tutor_branch_id": 1}

        response = self.client.post(self.register_url, data, format="json")

        # Проверяем, что статус ответа 201 (Created)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Проверяем, что преподаватель был создан в базе данных
        self.assertEqual(TutorProfile.objects.count(), 1)

        tutor = TutorProfile.objects.first()
        # Since phone number is cleaned in the serializer, compare with the cleaned version
        cleaned_phone = "".join(filter(str.isdigit, data["phone_number"]))
        self.assertEqual(tutor.phone_number, cleaned_phone)
        # Convert both values to string for comparison since branch might be stored as string
        self.assertEqual(str(tutor.branch), str(data["tutor_branch_id"]))

    def test_register_tutor_duplicate_phone(self):
        """
        Тест регистрации преподавателя с уже существующим номером телефона
        """
        # Сначала регистрируем преподавателя
        data = {"phone_number": "375 44 712 3218", "tutor_branch_id": 1}

        # Первый запрос должен быть успешным
        first_response = self.client.post(self.register_url, data, format="json")
        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)

        # Второй запрос с тем же номером должен вернуть ошибку
        second_response = self.client.post(self.register_url, data, format="json")
        self.assertEqual(second_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(second_response.data["detail"], "Phone number already registered")

    def test_register_tutor_invalid_data(self):
        """
        Тест регистрации преподавателя с невалидными данными
        """
        # Пропускаем обязательные поля
        data = {
            "phone_number": "375 44 712 3218"
            # tutor_branch_id отсутствует
        }

        response = self.client.post(self.register_url, data, format="json")

        # Проверяем, что статус ответа 400 (Bad Request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_tutor_missing_fields(self):
        """
        Тест регистрации преподавателя с отсутствующими полями
        """
        # Отправляем пустой запрос
        data = {}

        response = self.client.post(self.register_url, data, format="json")

        # Проверяем, что статус ответа 400 (Bad Request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class LoginTutorViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.login_url = reverse("tutor-login")
        self.register_url = reverse("tutor-register")

        self.tutor_patcher = patch("app_resumes.views.get_tutor_data_from_crm", side_effect=mock_get_tutor_data_from_crm)
        self.mock_get_tutor = self.tutor_patcher.start()

        # Register a tutor for login tests
        register_data = {"phone_number": "375447123218", "tutor_branch_id": 1}
        self.client.post(self.register_url, register_data, format="json")

    def tearDown(self):
        self.tutor_patcher.stop()

    def test_login_tutor_success(self):
        """
        Тест успешной авторизации преподавателя
        """
        data = {"phone_number": "375 44 712 3218"}  # Phone number with spaces should be cleaned

        response = self.client.post(self.login_url, data, format="json")

        # Проверяем, что статус ответа 200 (OK)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Проверяем, что в ответе есть токен
        self.assertIn("access_token", response.data)
        self.assertIn("token_type", response.data)
        self.assertEqual(response.data["token_type"], "bearer")

    def test_login_tutor_invalid_phone(self):
        """
        Тест авторизации преподавателя с неверным номером телефона
        """
        data = {"phone_number": "375447123219"}  # Non-existent phone number

        response = self.client.post(self.login_url, data, format="json")

        # Проверяем, что статус ответа 401 (Unauthorized)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["detail"], "Incorrect phone number")

    def test_login_tutor_invalid_data(self):
        """
        Тест авторизации преподавателя с невалидными данными
        """
        data = {"phone_number": ""}  # Empty phone number

        response = self.client.post(self.login_url, data, format="json")

        # Проверяем, что статус ответа 400 (Bad Request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TutorGroupsViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.register_url = reverse("tutor-register")
        self.login_url = reverse("tutor-login")
        self.groups_url = reverse("tutor-groups")

        self.tutor_patcher = patch("app_resumes.views.get_tutor_data_from_crm", side_effect=mock_get_tutor_data_from_crm)
        self.mock_get_tutor = self.tutor_patcher.start()

        # Register and login a tutor for groups tests
        register_data = {"phone_number": "375447123218", "tutor_branch_id": 1}
        self.client.post(self.register_url, register_data, format="json")

        login_data = {"phone_number": "375 44 712 3218"}
        login_response = self.client.post(self.login_url, login_data, format="json")

        # Set authorization header for subsequent requests
        self.token = login_response.data["access_token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")

    def tearDown(self):
        self.tutor_patcher.stop()

    def test_get_tutor_groups_success(self):
        """
        Тест получения групп преподавателя
        """
        response = self.client.get(self.groups_url)

        # Проверяем, что статус ответа 200 (OK)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Проверяем, что в ответе есть список групп (даже если пустой)
        # В зависимости от структуры ответа, проверяем наличие ключа 'groups' или проверяем тип данных
        if isinstance(response.data, dict):
            self.assertIn("groups", response.data)
        else:
            self.assertIsInstance(response.data, list)

    def test_get_tutor_groups_without_auth(self):
        """
        Тест получения групп преподавателя без аутентификации
        """
        # Сбрасываем авторизационный заголовок
        self.client.credentials()

        response = self.client.get(self.groups_url)

        # Проверяем, что статус ответа 401 (Unauthorized)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["detail"], "Authentication required")

    def test_login_tutor_missing_fields(self):
        """
        Тест авторизации преподавателя с отсутствующими полями
        """
        # Отправляем пустой запрос
        data = {}

        response = self.client.post(self.login_url, data, format="json")

        # Проверяем, что статус ответа 400 (Bad Request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class StudentForeignKeyModelTest(TestCase):
    """Тесты реляционных связей Resume/ParentReview → Student (ForeignKey)."""

    def setUp(self):
        self.group = Group.objects.create(
            crm_group_id=100,
            branch_ids=[1],
            teacher_ids=[1],
            name="Test Group",
            level_id=1,
            status_id=1,
            limit=10,
        )
        self.student = Student.objects.create(
            student_crm_id=9999,
            student_name="Тестовый Студент",
            group=self.group,
        )

    def test_resume_created_with_student_fk(self):
        """Резюме создаётся с FK на студента."""
        resume = Resume.objects.create(student=self.student, content="Тестовое резюме")
        self.assertEqual(resume.student, self.student)
        self.assertEqual(resume.student.student_crm_id, 9999)

    def test_parent_review_created_with_student_fk(self):
        """Отзыв создаётся с FK на студента."""
        review = ParentReview.objects.create(student=self.student, content="Тестовый отзыв")
        self.assertEqual(review.student, self.student)
        self.assertEqual(review.student.student_crm_id, 9999)

    def test_cascade_delete_resumes_on_student_delete(self):
        """При удалении студента каскадно удаляются все его резюме."""
        Resume.objects.create(student=self.student, content="Резюме 1")
        Resume.objects.create(student=self.student, content="Резюме 2")
        self.assertEqual(Resume.objects.filter(student=self.student).count(), 2)

        self.student.delete()
        self.assertEqual(Resume.objects.count(), 0)

    def test_cascade_delete_reviews_on_student_delete(self):
        """При удалении студента каскадно удаляются все его отзывы."""
        ParentReview.objects.create(student=self.student, content="Отзыв 1")
        ParentReview.objects.create(student=self.student, content="Отзыв 2")
        self.assertEqual(ParentReview.objects.filter(student=self.student).count(), 2)

        self.student.delete()
        self.assertEqual(ParentReview.objects.count(), 0)

    def test_cascade_delete_student_on_group_delete(self):
        """При удалении группы каскадно удаляются студенты, резюме и отзывы."""
        Resume.objects.create(student=self.student, content="Резюме")
        ParentReview.objects.create(student=self.student, content="Отзыв")

        self.group.delete()
        self.assertEqual(Student.objects.count(), 0)
        self.assertEqual(Resume.objects.count(), 0)
        self.assertEqual(ParentReview.objects.count(), 0)

    def test_reverse_relation_resumes(self):
        """Обратная связь student.resumes работает корректно."""
        Resume.objects.create(student=self.student, content="R1")
        Resume.objects.create(student=self.student, content="R2")
        self.assertEqual(self.student.resumes.count(), 2)

    def test_reverse_relation_parent_reviews(self):
        """Обратная связь student.parent_reviews работает корректно."""
        ParentReview.objects.create(student=self.student, content="PR1")
        self.assertEqual(self.student.parent_reviews.count(), 1)

    def test_resume_str(self):
        """__str__ модели Resume отображает crm_id студента."""
        resume = Resume.objects.create(student=self.student, content="test")
        self.assertEqual(str(resume), "Resume for student 9999")

    def test_parent_review_str(self):
        """__str__ модели ParentReview отображает crm_id студента."""
        review = ParentReview.objects.create(student=self.student, content="test")
        self.assertEqual(str(review), "Review for student 9999")


class ResumeSerializerTest(TestCase):
    """Тесты сериализатора ResumeSerializer (обратная совместимость API)."""

    def setUp(self):
        self.group = Group.objects.create(
            crm_group_id=200,
            branch_ids=[1],
            teacher_ids=[1],
            name="Serializer Group",
            level_id=1,
            status_id=1,
            limit=10,
        )
        self.student = Student.objects.create(
            student_crm_id=7777,
            student_name="Сериализуемый Студент",
            group=self.group,
        )
        self.resume = Resume.objects.create(
            student=self.student,
            content="Содержание резюме",
            is_verified=True,
        )

    def test_serializer_outputs_student_crm_id(self):
        """Сериализатор выводит поле student_crm_id (обратная совместимость)."""
        serializer = ResumeSerializer(self.resume)
        data = serializer.data
        self.assertIn("student_crm_id", data)
        self.assertEqual(data["student_crm_id"], 7777)
        # Поле student не должно быть в выводе
        self.assertNotIn("student", data)

    def test_serializer_accepts_student_crm_id_on_create(self):
        """Сериализатор принимает student_crm_id при создании (обратная совместимость)."""
        data = {"student_crm_id": 7777, "content": "Новое резюме"}
        serializer = ResumeSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        resume = serializer.save()
        self.assertEqual(resume.student, self.student)

    def test_serializer_rejects_nonexistent_student_crm_id(self):
        """Сериализатор отклоняет несуществующий student_crm_id."""
        data = {"student_crm_id": 99999, "content": "Несуществующий студент"}
        serializer = ResumeSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("student_crm_id", serializer.errors)


class ParentReviewSerializerTest(TestCase):
    """Тесты сериализатора ParentReviewSerializer."""

    def setUp(self):
        self.group = Group.objects.create(
            crm_group_id=300,
            branch_ids=[1],
            teacher_ids=[1],
            name="Review Group",
            level_id=1,
            status_id=1,
            limit=10,
        )
        self.student = Student.objects.create(
            student_crm_id=8888,
            student_name="Отзывчивый Студент",
            group=self.group,
        )

    def test_serializer_outputs_student_crm_id(self):
        """Сериализатор отзыва выводит student_crm_id."""
        review = ParentReview.objects.create(student=self.student, content="Отзыв")
        serializer = ParentReviewSerializer(review)
        data = serializer.data
        self.assertIn("student_crm_id", data)
        self.assertEqual(data["student_crm_id"], 8888)

    def test_serializer_create_review_via_crm_id(self):
        """Создание отзыва через сериализатор по student_crm_id."""
        data = {"student_crm_id": 8888, "content": "Новый отзыв от родителей"}
        serializer = ParentReviewSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        review = serializer.save()
        self.assertEqual(review.student, self.student)
        self.assertEqual(review.content, "Новый отзыв от родителей")


class ResumeAPIEndpointTest(TestCase):
    """Тесты API эндпоинтов для резюме с новой FK-структурой."""

    def setUp(self):
        self.client = APIClient()
        self.group = Group.objects.create(
            crm_group_id=400,
            branch_ids=[1],
            teacher_ids=[1],
            name="API Group",
            level_id=1,
            status_id=1,
            limit=10,
        )
        self.student = Student.objects.create(
            student_crm_id=5555,
            student_name="API Студент",
            group=self.group,
        )
        # Создаём тьютора и получаем токен
        self.tutor = TutorProfile.objects.create(
            tutor_crm_id="t1",
            tutor_name="Тьютор API",
            branch="1",
            is_senior=True,
            phone_number="1234567890",
        )
        from app_resumes.views import create_access_token
        self.token = create_access_token(data={"sub": self.tutor.phone_number})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")

    def test_get_latest_verified_resume(self):
        """Получение последнего верифицированного резюме по student_crm_id."""
        Resume.objects.create(student=self.student, content="Старое", is_verified=True)
        Resume.objects.create(student=self.student, content="Новое", is_verified=True)

        url = reverse("latest-verified-resume")
        response = self.client.get(url, {"student_crm_id": "5555"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["content"], "Новое")
        self.assertEqual(response.data["student_crm_id"], 5555)

    def test_get_latest_verified_resume_not_found(self):
        """404 при отсутствии верифицированных резюме."""
        url = reverse("latest-verified-resume")
        response = self.client.get(url, {"student_crm_id": "5555"})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_resume_with_valid_student(self):
        """Создание резюме через API по существующему student_crm_id."""
        url = reverse("create-resume")
        data = {"student_crm_id": "5555", "content": "Новое API резюме"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["student_crm_id"], 5555)

    def test_create_resume_with_invalid_student(self):
        """404 при создании резюме для несуществующего студента."""
        url = reverse("create-resume")
        data = {"student_crm_id": "99999", "content": "Не должно создаться"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_list_resumes_by_student_crm_id(self):
        """Фильтрация резюме по student_crm_id через query parameter."""
        Resume.objects.create(student=self.student, content="Резюме 1")
        Resume.objects.create(student=self.student, content="Резюме 2")

        url = reverse("client-resumes")
        response = self.client.get(url, {"student_crm_id": "5555"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)

    def test_create_parent_review_via_api(self):
        """Создание отзыва через API по student_crm_id."""
        url = reverse("create-parent-review")
        data = {"student_crm_id": 5555, "content": "Отличный курс!"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["student_crm_id"], 5555)
        self.assertEqual(response.data["content"], "Отличный курс!")

