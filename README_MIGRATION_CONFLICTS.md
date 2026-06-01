# Resolving Django Migration Conflicts (Diverged Migrations)

This guide explains how to resolve migration conflicts on the server if `makemigrations` has been run directly on the server database previously.

In Django, migration history must be a single, linear chain of files. If local and server environments have generated different migrations (creating "multiple migration heads"), copying new migrations from local to server will result in an error:
`django.db.migrations.exceptions.AmbiguityError: app_resumes has more than one migration head.`

To resolve this safely without breaking existing server data, follow this step-by-step sequencing guide.

---

## 🔍 Phase 1: Server Diagnostics

Before transferring any files, determine the exact state of migrations on the production server.

1. **Connect to the server** and navigate to your project directory.
2. **List all migration files** currently residing on the server:
   ```bash
   ls backend/app_resumes/migrations/
   ```
3. **Check applied migrations** in the server's database:
   ```bash
   python manage.py showmigrations app_resumes
   ```
   Identify the **last applied migration** (marked with `[X]`). 
   *For example, let's assume the last applied migration on the server is named:* `0009_server_custom`

---

## 🔗 Phase 2: Sequencing and Chaining New Migrations

To avoid conflicts, you must rename the three new local migrations and change their dependencies so they run **after** the server's last migration.

Our new migration files are:
- `0008_parentreview_student_resume_student.py`
- `0009_auto_20260525_1630.py` (data migration)
- `0010_remove_parentreview_student_crm_id_and_more.py`

### Step 1: Rename the Files
Rename the local files when copying them to the server directory so that their prefixes follow the server's last migration sequence number.

*Assuming the server's last migration prefix was `0009`:*
* Rename `0008_parentreview_student_resume_student.py` to **`0010_parentreview_student_resume_student.py`**
* Rename `0009_auto_20260525_1630.py` to **`0011_auto_20260525_1630.py`**
* Rename `0010_remove_parentreview_student_crm_id_and_more.py` to **`0012_remove_parentreview_student_crm_id_and_more.py`**

### Step 2: Update Dependencies in the First Migration
Open the first new migration file on the server (which is now `0010_parentreview_student_resume_student.py`).

Find the `dependencies` list:
```python
dependencies = [
    ('app_resumes', '0007_alter_student_options_student_study_start_date'),
]
```

Change it to reference the **last applied migration on the server** (e.g., `0009_server_custom`):
```python
dependencies = [
    ('app_resumes', '0009_server_custom'),  # Name of your server's last applied migration
]
```

### Step 3: Verify the Chained Dependencies in Subsequent Migrations
Verify that the renamed migrations point to their new predecessor:

1. Open `0011_auto_20260525_1630.py` and ensure it depends on `0010_parentreview_student_resume_student`:
   ```python
   dependencies = [
       ('app_resumes', '0010_parentreview_student_resume_student'),
   ]
   ```
2. Open `0012_remove_parentreview_student_crm_id_and_more.py` and ensure it depends on `0011_auto_20260525_1630`:
   ```python
   dependencies = [
       ('app_resumes', '0011_auto_20260525_1630'),
   ]
   ```

---

## 🚀 Phase 3: Applying Migrations Safely

Once the new sequence has been established:

1. **Back up the production database**:
   ```bash
   cp db.sqlite3 db.sqlite3.backup_before_fk
   ```
2. **Apply the migrations**:
   ```bash
   python manage.py migrate app_resumes
   ```
3. **Verify applied status**:
   Ensure all migrations are marked with `[X]`:
   ```bash
   python manage.py showmigrations app_resumes
   ```
   
Your server's database is now fully migrated and consistent with the new relational schema, running the custom data migration safely on top of your existing custom server schema.
