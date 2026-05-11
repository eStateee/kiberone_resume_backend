import os
from pathlib import Path
from dotenv import load_dotenv


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(os.path.join(BASE_DIR, ".env"))

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-q^d2*#x*-*eref=8tjm4(uj31976z5&%i#lt#-s482($8pt2o&")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv("DEBUG", "True").lower() == "true"

ALLOWED_HOSTS = ["kiber-resume.of.by", "185.244.50.19", "localhost", "127.0.0.1", "0.0.0.0", "93.85.88.72"]


# CORS settings for React application
CORS_ALLOWED_ORIGINS = [
    "http://kiber-resume.of.by",
    "https://kiber-resume.of.by",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://93.85.88.72",
    "https://93.85.88.72",
]

CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_ALL_ORIGINS = False

# CSRF settings for React application
CSRF_TRUSTED_ORIGINS = [
    "http://kiber-resume.of.by",
    "https://kiber-resume.of.by",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://93.85.88.72",
    "https://93.85.88.72",
]


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "app_resumes",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "_settings.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "_settings.wsgi.application"


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = "static/"
if DEBUG:
    STATICFILES_DIRS = [
        BASE_DIR / "static",
    ]
else:
    STATIC_ROOT = BASE_DIR / "static"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"


# DRF Configuration
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        # Custom JWT authentication will be handled in views
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}


# Redis settings
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")
REDIS_DB = os.getenv("REDIS_DB", "0")

# Настройки Celery
CELERY_BROKER_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_TIMEZONE = "Europe/Moscow"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60
# Хранение результатов задач в базе данных Django
CELERY_RESULT_BACKEND = "django-db"


CRM_API_URL = os.getenv("CRM_API_URL", "")
CRM_EMAIL = os.getenv("CRM_EMAIL", "")
CRM_API_KEY = os.getenv("CRM_API_KEY", "")
CRM_BRANCH_IDS = [int(b.strip()) for b in os.getenv("CRM_BRANCH_IDS", "1,2,3,4").split(",")]


LOGS_DIR = BASE_DIR / "logs"
os.makedirs(LOGS_DIR, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {filename} {lineno} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "file": {
            "level": "DEBUG",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOGS_DIR / "django.log",
            "maxBytes": 1024 * 1024,  # 1MB
            "backupCount": 5,
            "formatter": "verbose",
        },
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "root": {
        "handlers": ["file", "console"],
    },
    "loggers": {
        "django": {
            "handlers": ["file", "console"],
            "level": "INFO",
            "propagate": False,
        },
        "app_resume": {
            "handlers": ["file", "console"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}
