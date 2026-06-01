from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from .models import TutorProfile, Resume, ParentReview, Group, Student
from .serializers import (
    TutorProfileSerializer,
    ResumeSerializer,
    ParentReviewSerializer,
    GroupSerializer,
    StudentSerializer,
    TutorRegisterRequestSerializer,
    TutorLoginSerializer,
    ResumeUpdateSerializer,
    ResumeCreateSerializer,
    TokenSerializer,
)
from app_resumes.crm_integration import get_tutor_data_from_crm, get_client_data_from_crm, get_group_clients_from_crm, get_all_groups
import jwt
from django.conf import settings
from datetime import datetime, timedelta
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.http import JsonResponse


# JWT token creation utility
def create_access_token(data: dict):
    """Create JWT access token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=1)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
    return encoded_jwt


def decode_access_token(token: str):
    """Decode JWT access token"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.PyJWTError:
        return None


def get_current_user_from_request(request):
    """Extract current user from request using JWT token"""
    token = None
    auth_header = request.META.get("HTTP_AUTHORIZATION")
    if auth_header:
        try:
            token = auth_header.split(" ")[1]  # Bearer <token>
        except IndexError:
            return None

    if token:
        payload = decode_access_token(token)
        if payload:
            phone_number = payload.get("sub")
            if phone_number:
                try:
                    return TutorProfile.objects.get(phone_number=phone_number)
                except TutorProfile.DoesNotExist:
                    return None
    return None


def get_current_active_tutor(request):
    """Get current active tutor from request"""
    return get_current_user_from_request(request)


def get_current_senior_tutor(request):
    """Get current senior tutor from request"""
    tutor = get_current_user_from_request(request)
    if tutor and tutor.is_senior:
        return tutor
    return None


def authenticate_tutor(phone_number: str):
    """Authenticate tutor by phone number"""
    try:
        return TutorProfile.objects.get(phone_number=phone_number)
    except TutorProfile.DoesNotExist:
        return None


def get_tutor_by_phone_number(phone_number: str):
    """Get tutor by phone number"""
    try:
        return TutorProfile.objects.get(phone_number=phone_number)
    except TutorProfile.DoesNotExist:
        return None


# Health check endpoint
@api_view(["GET"])
def health_check(request):
    """Health check endpoint"""
    return Response({"status": "ok", "message": "Backend is working"})


# Test endpoint
@api_view(["GET"])
def test_endpoint(request):
    """Test endpoint"""
    return Response({"message": "Hello from Django REST Framework"})


# Tutor registration
@api_view(["POST"])
def register_tutor(request):
    """
    Register a new tutor

    This endpoint registers a new tutor by validating their phone number and tutor branch ID,
    fetching their data from the CRM system, and creating a new TutorProfile in the database.

    Required parameters:
    - phone_number: The tutor's phone number for identification
    - tutor_branch_id: The branch ID where the tutor is registered in the CRM

    Returns:
    - 201 Created: If the tutor is successfully registered with their profile data
    - 400 Bad Request: If the phone number is already registered or validation fails
    - 404 Not Found: If the tutor is not found in the CRM system

    Example request body:
    {
        "phone_number": "+79991234567",
        "tutor_branch_id": 1
    }
    """
    serializer = TutorRegisterRequestSerializer(data=request.data)
    if serializer.is_valid():
        phone_number = serializer.validated_data["phone_number"]
        tutor_branch_id = serializer.validated_data["tutor_branch_id"]

        # Check if tutor with this phone number already exists
        existing_phone_tutor = get_tutor_by_phone_number(phone_number)
        if existing_phone_tutor:
            return Response({"detail": "Phone number already registered"}, status=status.HTTP_400_BAD_REQUEST)

        # Get tutor data from CRM
        tutor_data = get_tutor_data_from_crm(phone_number, tutor_branch_id)

        if not tutor_data:
            return Response({"detail": "Tutor not found in CRM"}, status=status.HTTP_404_NOT_FOUND)

        # Extract all fields from CRM data with proper error handling
        tutor_crm_id = tutor_data.get("id", None)
        tutor_name = tutor_data.get("name", None)
        branch_ids = tutor_data.get("branch_ids", None)
        dob = tutor_data.get("dob", None)
        gender = tutor_data.get("gender", None)
        streaming_id = tutor_data.get("streaming_id", None)
        note = tutor_data.get("note", None)
        e_date = tutor_data.get("e_date", None)
        avatar_url = tutor_data.get("avatar_url", None)
        phone = tutor_data.get("phone", None)
        email = tutor_data.get("email", None)
        web = tutor_data.get("web", None)
        addr = tutor_data.get("addr", None)
        teacher_to_skill = tutor_data.get("teacher-to-skill", None)

        # Validate required fields to avoid potential database errors
        if tutor_crm_id is not None:
            try:
                tutor_crm_id = int(tutor_crm_id) if str(tutor_crm_id).isdigit() else None
            except (ValueError, TypeError):
                tutor_crm_id = None

        # Create or update tutor profile with all CRM data
        db_tutor = TutorProfile.objects.create(
            tutor_crm_id=tutor_crm_id,
            tutor_name=tutor_name,
            branch=tutor_branch_id,
            is_senior=False,
            phone_number=phone_number,
            # Additional fields from CRM
            branch_ids=branch_ids,
            dob=dob,
            gender=gender,
            streaming_id=streaming_id,
            note=note,
            e_date=e_date,
            avatar_url=avatar_url,
            phone=phone,
            email=email,
            web=web,
            addr=addr,
            teacher_to_skill=teacher_to_skill,
        )

        tutor_serializer = TutorProfileSerializer(db_tutor)
        return Response(tutor_serializer.data, status=status.HTTP_201_CREATED)
    else:
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Tutor login
@api_view(["POST"])
def login_tutor(request):
    """
    Login a tutor

    This endpoint logs in a tutor by validating their phone number,
    fetching their updated data from the CRM system, and creating a JWT token
    for authentication in subsequent requests.

    Required parameters:
    - phone_number: The tutor's phone number for identification

    Returns:
    - 200 OK: If the tutor is successfully authenticated with JWT token
    - 400 Bad Request: If validation fails
    - 401 Unauthorized: If the phone number is incorrect or tutor not found

    Example request body:
    {
        "phone_number": "+79991234567"
    }
    """
    serializer = TutorLoginSerializer(data=request.data)
    if serializer.is_valid():
        phone_number = serializer.validated_data["phone_number"]
        tutor = authenticate_tutor(phone_number)
        if not tutor:
            return Response({"detail": "Incorrect phone number"}, status=status.HTTP_401_UNAUTHORIZED)

        # Get updated tutor data from CRM and update DB record
        if tutor.branch:
            tutor_data = get_tutor_data_from_crm(tutor.phone_number, tutor.branch)
            if tutor_data:
                # Update tutor profile with latest CRM data
                update_data = {}
                update_data["tutor_crm_id"] = tutor_data.get("id")
                update_data["tutor_name"] = tutor_data.get("name")
                update_data["branch_ids"] = tutor_data.get("branch_ids")
                update_data["dob"] = tutor_data.get("dob")
                update_data["gender"] = tutor_data.get("gender")
                update_data["streaming_id"] = tutor_data.get("streaming_id")
                update_data["note"] = tutor_data.get("note")
                update_data["e_date"] = tutor_data.get("e_date")
                update_data["avatar_url"] = tutor_data.get("avatar_url")
                update_data["phone"] = tutor_data.get("phone")
                update_data["email"] = tutor_data.get("email")
                update_data["web"] = tutor_data.get("web")
                update_data["addr"] = tutor_data.get("addr")
                update_data["teacher_to_skill"] = tutor_data.get("teacher-to-skill")

                # Update the tutor record with new CRM data
                for field, value in update_data.items():
                    setattr(tutor, field, value)

                tutor.save()

        # Create JWT token
        access_token = create_access_token(data={"sub": tutor.phone_number})
        token_serializer = TokenSerializer(data={"access_token": access_token, "token_type": "bearer"})
        if token_serializer.is_valid():
            return Response({"access_token": access_token, "token_type": "bearer"})
        else:
            return Response({"access_token": access_token, "token_type": "bearer"})
    else:
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
def get_tutor_groups(request):
    """
    Get tutor groups

    This endpoint returns the list of groups associated with the authenticated tutor.
    Senior tutors can see all groups, while regular tutors can only see groups they are assigned to.

    Authentication:
    - Requires a valid JWT token in the Authorization header
    - Token is obtained through the login endpoint

    Returns:
    - 200 OK: List of groups associated with the tutor
    - 401 Unauthorized: If the tutor is not authenticated

    Response format:
    [
        {
            "id": group_id,
            "branch_ids": [branch_id1, branch_id2, ...],
            "teacher_ids": [teacher_id1, teacher_id2, ...],
            "name": "Group Name",
            "level_id": level_id,
            "status_id": status_id,
            "company_id": company_id,
            "streaming_id": streaming_id,
            "limit": max_students_count,
            "note": "Additional notes",
            "b_date": "start_date",
            "e_date": "end_date",
            "created_at": "creation_timestamp",
            "updated_at": "update_timestamp",
            "custom_aerodromnaya": "custom_field_value"
        },
        ...
    ]
    """
    current_tutor = get_current_active_tutor(request)
    if not current_tutor:
        return Response({"detail": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

    if current_tutor.is_senior:
        groups = Group.objects.all()
    else:
        # Получаем все группы и фильтруем в Python
        all_groups = Group.objects.all()
        tutor_name = current_tutor.tutor_name
        groups = []
        for group in all_groups:
            # Проверяем, содержится ли имя преподавателя в JSON-массиве teacher_ids
            if tutor_name in group.teacher_ids:
                groups.append(group)

    groups_data = []
    for group in groups:
        group_data = {
            "id": group.crm_group_id,
            "branch_ids": group.branch_ids,
            "teacher_ids": group.teacher_ids,
            "name": group.name,
            "level_id": group.level_id,
            "status_id": group.status_id,
            "company_id": group.company_id,
            "streaming_id": group.streaming_id,
            "limit": group.limit,
            "note": group.note,
            "b_date": group.b_date,
            "e_date": group.e_date,
            "created_at": group.created_at,
            "updated_at": group.updated_at,
            "custom_aerodromnaya": group.custom_aerodromnaya,
        }
        groups_data.append(group_data)

    return Response(groups_data if groups_data else {"groups": []})


@api_view(["GET"])
def get_group_clients(request):
    """
    Get clients in a group

    This endpoint returns the list of clients (students) associated with a specific group.
    The endpoint requires authentication and the group ID should be provided as a query parameter.

    Query parameters:
    - group_id: The ID of the group to retrieve clients for

    Authentication:
    - Requires a valid JWT token in the Authorization header
    - Token is obtained through the login endpoint

    Returns:
    - 200 OK: List of clients associated with the group
    - 401 Unauthorized: If the tutor is not authenticated
    - 404 Not Found: If the group does not exist or no clients found

    Response format:
    [
        {
            "customer_id": student_crm_id,
            "client_name": student_name
        },
        ...
    ]

    Example request:
    GET /api/app_resumes/groups/clients/?group_id=1
    Authorization: Bearer <jwt_token>
    """
    group_id = request.GET.get("group_id", "")
    current_tutor = get_current_active_tutor(request)
    if not current_tutor:
        return Response({"detail": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

    try:
        # Convert group_id to integer for database query
        group_id_int = int(group_id)

        # Get the group from database
        group = Group.objects.get(crm_group_id=group_id_int)

        # Get all students associated with this group
        students = Student.objects.filter(group=group)

        # Format the response to match the expected structure
        clients_data = []
        for student in students:
            client_data = {
                "customer_id": student.student_crm_id,
                "client_name": student.student_name,
                "study_start_date": student.study_start_date,
            }
            clients_data.append(client_data)

        return Response(clients_data if clients_data else {"clients": []})
    except ValueError:
        # Handle case where group_id is not a valid integer
        return Response({"clients": []})
    except Group.DoesNotExist:
        return Response({"clients": []})
    except Exception as e:
        # Handle any other errors
        return Response({"clients": []})


# Resume endpoints
class ResumeListView(generics.ListAPIView):
    """
    Get resumes for a specific client

    This endpoint returns the list of resumes associated with a specific student.
    The endpoint requires authentication and the student CRM ID should be provided as a query parameter.

    Query parameters:
    - student_crm_id: The CRM ID of the student to retrieve resumes for

    Authentication:
    - Requires a valid JWT token in the Authorization header
    - Token is obtained through the login endpoint

    Returns:
    - 200 OK: List of resumes associated with the student
    - 401 Unauthorized: If the tutor is not authenticated

    Response format:
    [
        {
            "id": resume_id,
            "student_crm_id": student_crm_id,
            "content": "Resume content...",
            "is_verified": true/false,
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-01T00:00:00Z"
        },
        ...
    ]

    Example request:
    GET /api/app_resumes/resumes/client/?student_crm_id=12345
    Authorization: Bearer <jwt_token>
    """

    serializer_class = ResumeSerializer

    def get_queryset(self):
        current_tutor = get_current_active_tutor(self.request)
        if not current_tutor:
            return Resume.objects.none()

        student_crm_id = self.request.query_params.get("student_crm_id", "")
        return Resume.objects.filter(student__student_crm_id=student_crm_id).select_related("student")


class ResumeDetailView(APIView):
    """
    Update a specific resume

    This endpoint allows updating a specific resume by its ID.
    The endpoint requires authentication and accepts PUT requests with resume data.

    Path parameters:
    - resume_id: The ID of the resume to update

    Authentication:
    - Requires a valid JWT token in the Authorization header
    - Token is obtained through the login endpoint

    Request body:
    - content: Updated resume content (optional)
    - is_verified: Verification status (optional)

    Returns:
    - 200 OK: Updated resume data
    - 400 Bad Request: If the provided data is invalid
    - 401 Unauthorized: If the tutor is not authenticated
    - 404 Not Found: If the resume does not exist

    Response format:
    {
        "id": resume_id,
        "student_crm_id": student_crm_id,
        "content": "Updated resume content...",
        "is_verified": true/false,
        "created_at": "2023-01-01T00:00Z",
        "updated_at": "2023-01-01T00:00Z"
    }

    Example request:
    PUT /api/app_resumes/resumes/1/
    Authorization: Bearer <jwt_token>
    {
        "content": "Updated resume content",
        "is_verified": true
    }
    """

    def put(self, request, resume_id):
        current_tutor = get_current_active_tutor(request)
        if not current_tutor:
            return Response({"detail": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

        resume = get_object_or_404(Resume, id=resume_id)

        serializer = ResumeUpdateSerializer(data=request.data)
        if serializer.is_valid():
            # Update the resume
            if "content" in serializer.validated_data:
                resume.content = serializer.validated_data["content"]

            resume.save()
            resume_serializer = ResumeSerializer(resume)
            return Response(resume_serializer.data)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VerifyResumeView(APIView):
    """
    Verify a specific resume (requires senior tutor)

    This endpoint allows a senior tutor to verify a specific resume by its ID.
    The endpoint requires authentication as a senior tutor and accepts POST requests.

    Path parameters:
    - resume_id: The ID of the resume to verify

    Authentication:
    - Requires a valid JWT token in the Authorization header
    - Token is obtained through the login endpoint
    - Only senior tutors have access to this endpoint

    Returns:
    - 200 OK: Verified resume data
    - 403 Forbidden: If the tutor is not a senior tutor
    - 404 Not Found: If the resume does not exist

    Response format:
    {
        "id": resume_id,
        "student_crm_id": student_crm_id,
        "content": "Resume content...",
        "is_verified": true,
        "created_at": "2023-01-01T00:00Z",
        "updated_at": "2023-01-01T00:00Z"
    }

    Example request:
    POST /api/app_resumes/resumes/1/verify/
    Authorization: Bearer <jwt_token>
    """

    def post(self, request, resume_id):
        current_tutor = get_current_senior_tutor(request)
        if not current_tutor:
            return Response({"detail": "Senior tutor access required"}, status=status.HTTP_403_FORBIDDEN)

        resume = get_object_or_404(Resume, id=resume_id)

        # Update the resume verification status
        resume.is_verified = True
        resume.save()
        resume_serializer = ResumeSerializer(resume)
        return Response(resume_serializer.data)


class UnverifiedResumesView(generics.ListAPIView):
    """Get all unverified resumes"""

    serializer_class = ResumeSerializer

    def get_queryset(self):
        current_tutor = get_current_active_tutor(self.request)
        if not current_tutor:
            return Resume.objects.none()

        return Resume.objects.filter(is_verified=False)

    pagination_class = None


@api_view(["POST"])
def create_resume(request):
    """
    Create a new resume

    This endpoint allows creating a new resume for a student.
    The endpoint requires authentication and accepts POST requests with resume data.

    Authentication:
    - Requires a valid JWT token in the Authorization header
    - Token is obtained through the login endpoint

    Request body:
    - student_crm_id: The CRM ID of the student (required)
    - content: Resume content (required)
    - is_verified: Verification status (optional, default: False)

    Returns:
    - 201 Created: Created resume data
    - 40 Bad Request: If the provided data is invalid
    - 401 Unauthorized: If the tutor is not authenticated

    Response format:
    {
        "id": resume_id,
        "student_crm_id": student_crm_id,
        "content": "Resume content...",
        "is_verified": true/false,
        "created_at": "2023-01-01T00:00Z",
        "updated_at": "2023-01-01T00:00Z"
    }

    Example request:
    POST /api/app_resumes/resumes/
    Authorization: Bearer <jwt_token>
    {
        "student_crm_id": "12345",
        "content": "Student resume content...",
    }
    """
    current_tutor = get_current_active_tutor(request)
    if not current_tutor:
        return Response({"detail": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

    serializer = ResumeCreateSerializer(data=request.data)
    if serializer.is_valid():
        try:
            student = Student.objects.get(student_crm_id=int(serializer.validated_data["student_crm_id"]))
        except (ValueError, TypeError, Student.DoesNotExist):
            return Response({"detail": "Student not found in the local database"}, status=status.HTTP_404_NOT_FOUND)

        resume = Resume.objects.create(
            student=student,
            content=serializer.validated_data["content"],
        )
        resume_serializer = ResumeSerializer(resume)
        return Response(resume_serializer.data, status=status.HTTP_201_CREATED)
    else:
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["DELETE"])
def delete_resume(request, resume_id):
    """
    Delete a specific resume

    This endpoint allows deleting a specific resume by its ID.
    The endpoint requires authentication as a senior tutor and accepts DELETE requests.

    Path parameters:
    - resume_id: The ID of the resume to delete

    Authentication:
    - Requires a valid JWT token in the Authorization header
    - Token is obtained through the login endpoint
    - Only senior tutors have access to this endpoint

    Returns:
    - 200 OK: Confirmation that the resume was deleted
    - 403 Forbidden: If the tutor is not a senior tutor
    - 404 Not Found: If the resume does not exist

    Response format:
    {
        "message": "Resume deleted successfully"
    }

    Example request:
    DELETE /api/app_resumes/resumes/1/delete/
    Authorization: Bearer <jwt_token>
    """
    current_tutor = get_current_active_tutor(request)
    if not current_tutor:
        return Response({"detail": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

    if not current_tutor.is_senior:
        return Response({"detail": "Senior tutor access required"}, status=status.HTTP_403_FORBIDDEN)

    resume = get_object_or_404(Resume, id=resume_id)
    resume.delete()
    return Response({"message": "Resume deleted successfully"})


@api_view(["GET"])
def get_latest_verified_resume(request):
    """
    Get the latest verified resume for a specific student

    This endpoint returns the most recent verified resume associated with a specific student.
    The endpoint is accessible without authentication and the student CRM ID should be provided as a query parameter.

    Query parameters:
    - student_crm_id: The CRM ID of the student to retrieve the latest verified resume for

    Returns:
    - 200 OK: Latest verified resume data
    - 404 Not Found: If no verified resume is found for the student

    Response format:
    {
        "id": resume_id,
        "student_crm_id": student_crm_id,
        "content": "Resume content...",
        "is_verified": true,
        "created_at": "2023-01-01T00:00Z",
        "updated_at": "2023-01-01T00:00Z"
    }

    Example request:
    GET /api/app_resumes/resumes/latest-verified/?student_crm_id=12345
    """
    student_crm_id = request.GET.get("student_crm_id", "")
    if not student_crm_id:
        return Response({"detail": "student_crm_id parameter is required"}, status=status.HTTP_400_BAD_REQUEST)

    # Get the latest verified resume for the student
    latest_resume = Resume.objects.filter(student__student_crm_id=student_crm_id, is_verified=True).select_related("student").order_by("-created_at").first()

    if not latest_resume:
        return Response({"detail": "No verified resume found for this student"}, status=status.HTTP_404_NOT_FOUND)

    resume_serializer = ResumeSerializer(latest_resume)
    return Response(resume_serializer.data)


# Review endpoints
@api_view(["POST"])
def create_parent_review(request):
    """
    Create a new parent review

    This endpoint allows creating a new parent review for a student.
    The endpoint is accessible without authentication and accepts POST requests with review data.

    Request body:
    - student_crm_id: The CRM ID of the student (required)
    - content: Review content (required)

    Returns:
    - 201 Created: Created review data
    - 400 Bad Request: If the provided data is invalid

    Response format:
    {
        "id": review_id,
        "student_crm_id": student_crm_id,
        "content": "Review content...",
        "created_at": "2023-01-01T00:00Z",
        "updated_at": "2023-01-01T00:00Z"
    }

    Example request:
    POST /api/app_resumes/reviews/
    {
        "student_crm_id": "12345",
        "content": "Parent review content..."
    }
    """
    serializer = ParentReviewSerializer(data=request.data)
    if serializer.is_valid():
        review = serializer.save()
        review_serializer = ParentReviewSerializer(review)
        return Response(review_serializer.data, status=status.HTTP_201_CREATED)
    else:
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ParentReviewsView(generics.ListAPIView):
    """Get parent reviews for a specific student"""

    serializer_class = ParentReviewSerializer

    def get_queryset(self):
        current_tutor = get_current_active_tutor(self.request)
        if not current_tutor:
            return ParentReview.objects.none()

        student_crm_id = self.kwargs.get("student_crm_id", "")
        return ParentReview.objects.filter(student__student_crm_id=student_crm_id).select_related("student")


# Tutor detail endpoint
@api_view(["GET"])
def get_tutor_detail(request):
    """Get tutor details"""
    current_tutor = get_current_active_tutor(request)
    if not current_tutor:
        return Response({"detail": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

    # Return tutor details from the local database
    return Response(
        {
            "id": current_tutor.tutor_crm_id,
            "name": current_tutor.tutor_name,
            "branch_ids": current_tutor.branch_ids,
            "branch": current_tutor.branch,
            "dob": current_tutor.dob,
            "gender": current_tutor.gender,
            "streaming_id": current_tutor.streaming_id,
            "note": current_tutor.note,
            "e_date": current_tutor.e_date,
            "avatar_url": current_tutor.avatar_url,
            "phone": current_tutor.phone,
            "email": current_tutor.email,
            "web": current_tutor.web,
            "addr": current_tutor.addr,
            "teacher-to-skill": current_tutor.teacher_to_skill,
            "is_senior": current_tutor.is_senior,
        }
    )


# Client detail endpoint
@api_view(["GET"])
def get_client_detail(request):
    """
    Get client details

    This endpoint fetches detailed information about a specific client from the CRM system.
    The endpoint requires authentication and the student CRM ID should be provided as a query parameter.

    Query parameters:
    - student_crm_id: The CRM ID of the student to retrieve details for

    Authentication:
    - Requires a valid JWT token in the Authorization header
    - Token is obtained through the login endpoint

    Returns:
    - 200 OK: Client details from the CRM system
    - 401 Unauthorized: If the tutor is not authenticated
    - 404 Not Found: If the client is not found in the CRM system

    Response format:
    {
        "id": client_id,
        "name": client_name,
        "phone": ["+79991234567"],
        "email": ["client@example.com"],
        ...
    }

    Example request:
    GET /api/app_resumes/clients/detail/?student_crm_id=12345
    Authorization: Bearer <jwt_token>
    """
    current_tutor = get_current_active_tutor(request)
    if not current_tutor:
        return Response({"detail": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

    student_crm_id = request.GET.get("student_crm_id", "")

    # Integrate with CRM to get client details
    if current_tutor.branch:
        client_data = get_client_data_from_crm(student_crm_id, current_tutor.branch)
        if client_data:
            return Response(client_data)

    # Fallback response if CRM integration fails
    return Response({"client_detail": {}})
