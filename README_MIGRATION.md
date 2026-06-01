# Database Schema Migration & Fixes Report

This document outlines the database schema transition to relational constraints (Foreign Keys), the issues identified and resolved, and instructions for running and verifying the database migrations locally and on the server.

---

## 🛠️ Resolved Issues

During the audit of the schema changes and project files, the following issues were identified and resolved:

### 1. Fixed Bad Status Code Reference in `views.py`
* **File:** `app_resumes/views.py` (Line 530)
* **Problem:** The view return statement referenced `status.HTTP_40_BAD_REQUEST`, which is an invalid status code in Django REST Framework. This would cause a runtime crash (`AttributeError`) whenever the serializer validation failed during a resume update request.
* **Fix:** Corrected the status code to `status.HTTP_400_BAD_REQUEST`.

### 2. Resolved Local Test Suite Redis/Network Dependencies
* **File:** `app_resumes/tests.py`
* **Problem:** Running unit tests locally threw 8 errors because the tutor registration and authentication endpoints were trying to contact the real AlfaCRM API and cache tokens in a local Redis database (`redis.exceptions.ConnectionError: Error 10061 connecting to localhost:6379`). This made the test suite unusable without setting up infrastructure.
* **Fix:** Introduced an isolated mock for the external CRM API function `get_tutor_data_from_crm` in the view tests setup. 
* **Result:** All 30 unit tests now run and pass successfully in less than 0.2 seconds without requiring Redis or an internet connection.

---

## 💾 Database Schema Migration Process

The transition from the string-based `student_crm_id` to a Foreign Key relation with `Student` is performed via three sequential migrations:

1. **`0008_parent_review_student_resume_student.py`**
   * Adds the nullable `student` ForeignKey fields (`null=True`) on `Resume` and `ParentReview` pointing to the `Student` model.
2. **`0009_auto_20260525_1630.py` (Data Migration)**
   * Sequentially links existing `Resume` and `ParentReview` objects to `Student` objects by parsing their old string-based `student_crm_id` and looking up matching students.
   * Orphaned records (where the student no longer exists in the local database) are automatically pruned to prevent relational integrity errors.
3. **`0010_remove_parentreview_student_crm_id_and_more.py`**
   * Permanently drops the legacy `student_crm_id` columns from both tables.
   * Alters the new `student` ForeignKey fields to `null=False` (not null) and configures `on_delete=models.CASCADE` to enable automatic cascade deletion.

---

## 💻 How to Run and Verify Migrations Locally

All migrations are **already applied** on your local database (`db.sqlite3`). You can verify their status by running:

```bash
# Activate virtual environment
venv\Scripts\activate

# Show migration status
python manage.py showmigrations app_resumes
```

If you wish to test the migration process from scratch on a copy of your database:

### Step 1: Back up the database
Make sure you have a safe copy of your current SQLite database.
```bash
copy db.sqlite3 db.sqlite3.backup
```

### Step 2: Rollback the migrations
Roll back the database schema to before the Foreign Key migration:
```bash
python manage.py migrate app_resumes 0007
```
*(This reverts the schema and clears the foreign key columns).*

### Step 3: Run the migrations again
Apply the new migrations to execute the schema changes and data migration:
```bash
python manage.py migrate app_resumes
```
Review the console output to verify that the data migration runs successfully and links the records.

### Step 4: Verify the unit tests
Ensure all tests pass successfully:
```bash
python manage.py test
```

---

## 🚀 How to Run Migrations on the Server (Production)

Follow these steps to safely apply the changes to your production server:

### Step 1: Connect to the server
Log in to your VPS via SSH:
```bash
ssh user@your-vps-ip
```

### Step 2: Navigate to the backend directory
```bash
cd /path/to/resume/backend
```

### Step 3: Create a database backup
Always backup your database before running migrations in production.
```bash
cp db.sqlite3 db.sqlite3.backup_$(date +%Y%m%d_%H%M%S)
```

### Step 4: Pull the latest code changes
Retrieve the updated code containing the view fixes and mocked tests.
```bash
git pull origin main
```

> [!WARNING]
> **DO NOT** run `makemigrations` on the production server. You must deploy all migration files generated locally (including `0008`, `0009` (data migration), and `0010`) via Git. Running `makemigrations` on the server will fail because:
> 1. It cannot auto-generate the custom python data migration logic (`0009_auto_20260525_1630.py`), leading to `IntegrityError` and data loss.
> 2. It will cause conflicts in migration history and tables already existing in the database.


### Step 5: Activate the virtual environment
```bash
source venv/bin/activate
```

### Step 6: Apply the migrations
Run Django's migration command to automatically create the foreign keys, migrate the values, and drop the legacy columns:
```bash
python manage.py migrate app_resumes
```

### Step 7: Restart services
Restart backend services to apply the updated code:
```bash
sudo systemctl restart gunicorn
# or if using supervisor:
# supervisorctl restart gunicorn
```

### Step 8: Verify database integrity (Optional)
Run a quick query inside Django shell to verify there are no orphaned records:
```bash
python manage.py shell -c "
from app_resumes.models import Resume, Student
resume_ids = set(Resume.objects.values_list('student_id', flat=True))
student_ids = set(Student.objects.values_list('id', flat=True))
orphans = resume_ids - student_ids
print(f'Orphaned Resumes: {len(orphans)}')
"
```
*(The count should be 0).*
