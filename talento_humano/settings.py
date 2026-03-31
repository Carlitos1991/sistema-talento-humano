import os
import sys
from pathlib import Path
from decouple import config
from dotenv import load_dotenv

load_dotenv()
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, os.path.join(BASE_DIR, 'apps'))

# Configuración de Media (Archivos subidos por usuario)
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY')
# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# Evita advertencias COOP en desarrollo HTTP local.
if DEBUG:
    SECURE_CROSS_ORIGIN_OPENER_POLICY = None

ALLOWED_HOSTS = ['*']

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core',
    'security',
    'person',
    'employee',
    'institution',
    'budget',
    'schedule',
    'contract',
    'function_manual',
    'biometric',
    'personnel_actions',
    'payroll',
    'accounting',
    'permitrequest',
    'vacation',
    'sanctions',
    'documents'
]
AUTH_USER_MODEL = 'core.User'
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.core.middleware.SIGETHSecurityMiddleware',
]
# ==========================================
# CONFIGURACIÓN DE CORREO ELECTRÓNICO (ZIMBRA)
# ==========================================
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'mail.loja.gob.ec')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
# Configuramos la seguridad leyendo strings y convirtiéndolos a booleanos
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_USE_SSL = os.environ.get('EMAIL_USE_SSL', 'False') == 'True'

# El remitente oficial que verán los empleados
DEFAULT_FROM_EMAIL = f"Municipio de Loja - Nómina <{EMAIL_HOST_USER}>"

ROOT_URLCONF = 'talento_humano.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates']
        ,
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.navbar_notifications',
            ],
        },
    },
]

WSGI_APPLICATION = 'talento_humano.wsgi.application'

# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST'),
        'PORT': config('DB_PORT'),
    },
    'old_db': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'db_talento_2020',  # El nombre de la base vieja
        'USER': 'postgres',
        'PASSWORD': r'Talento2023**',
        'HOST': '192.168.1.253',  # La IP del servidor donde está la BD vieja
        'PORT': '5432',
    }
}

# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'es-ar'

TIME_ZONE = 'America/Guayaquil'
USE_THOUSAND_SEPARATOR = False
THOUSAND_SEPARATOR = '.'
DECIMAL_SEPARATOR = ','
NUMBER_GROUPING = 3
USE_I18N = True

USE_TZ = False

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

# Configuración de Archivos Estáticos
# Usar ruta absoluta para evitar URLs relativas que causen 404 en subpaths
STATIC_URL = '/static/'

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')  # Para producción

# Configuración de WhiteNoise para archivos estáticos en producción
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# --- CONFIGURACIÓN DE DURACIÓN DE SESIÓN ---
# Cierra la sesión después de 12 horas de inactividad.
SESSION_COOKIE_AGE = 43200  # 12 horas en segundos
# Actualiza la vida de la sesión con cada petición.
SESSION_SAVE_EVERY_REQUEST = True

# --- CONFIGURACIÓN DE AUTENTICACIÓN PERSONALIZADA ---

# 1. URL a la que redirige si el usuario intenta entrar a una zona privada sin loguearse
LOGIN_URL = 'core:login'

# 2. URL a la que va el usuario una vez se loguea correctamente
LOGIN_REDIRECT_URL = 'core:dashboard'

# 3. URL a la que va el usuario tras cerrar sesión
LOGOUT_REDIRECT_URL = 'core:login'
