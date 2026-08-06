import os
import sys
from pathlib import Path
from decouple import config
from dotenv import load_dotenv

load_dotenv()
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, os.path.join(BASE_DIR, 'apps'))

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
SECRET_KEY = config('SECRET_KEY')
DEBUG = 'True'
if DEBUG:
    SECURE_CROSS_ORIGIN_OPENER_POLICY = None

ALLOWED_HOSTS = [host.strip() for host in os.environ.get('ALLOWED_HOSTS', '*').split(',') if host.strip()]

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True

if os.environ.get('ENABLE_HTTPS_SECURITY', 'False') == 'True':
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False

    SESSION_COOKIE_SAMESITE = 'Lax'
    CSRF_COOKIE_SAMESITE = 'Lax'

if os.environ.get('ENABLE_HTTPS_SECURITY', 'False') == 'True':
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = 'None'
    CSRF_COOKIE_SAMESITE = 'None'

CSRF_TRUSTED_ORIGINS = ['https://rrhh.loja.gob.ec']

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
    'documents',
    'employee_archive',
    'mozilla_django_oidc',
]
AUTH_USER_MODEL = 'core.User'
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
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
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_USE_SSL = os.environ.get('EMAIL_USE_SSL', 'False') == 'True'

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
                'core.context_processors.system_branding',
                'core.context_processors.employee_archive_notifications',
                'core.context_processors.contract_notifications',
                'security.context_processors.help_messages_notifications',
                'sanctions.context_processors.pending_assignments',
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
        'NAME': 'db_talento_2020',
        'USER': 'postgres',
        'PASSWORD': r'Talento2023**',
        'HOST': '192.168.1.253',
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

# Configuración de Archivos Estáticos
STATIC_URL = '/static/'

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# --- CONFIGURACIÓN DE DURACIÓN DE SESIÓN ---
# Cierra la sesión después de 12 horas de inactividad.
SESSION_COOKIE_AGE = 43200  # 12 horas en segundos
# Actualiza la vida de la sesión con cada petición.
SESSION_SAVE_EVERY_REQUEST = True

# --- CONFIGURACIÓN DE AUTENTICACIÓN PERSONALIZADA ---

AUTHENTICATION_BACKENDS = (
    # 1. Login por nuestro propio formulario (login.html) -> valida
    #    usuario/contraseña DIRECTAMENTE contra Keycloak (grant 'password' /
    #    ROPC). Keycloak es la fuente de verdad de la contraseña.
    'core.auth.KeycloakPasswordBackend',
    # 2. Login SSO por redirect a la pantalla hospedada de Keycloak
    #    (mozilla-django-oidc). Sigue existiendo como flujo aparte.
    'core.auth.KeycloakOIDCBackend',
    # 3. Respaldo de emergencia SOLO para cuentas que todavía no viven en
    #    Keycloak (p.ej. un superusuario local de Django). Si quieres que
    #    Keycloak sea la ÚNICA fuente de verdad sin excepciones, elimina
    #    esta línea (pero perderás el acceso de emergencia a /admin/ para
    #    cuentas no sincronizadas).
    'django.contrib.auth.backends.ModelBackend',
)

# 1. URL a la que redirige si el usuario intenta entrar a una zona privada sin loguearse
LOGIN_URL = 'core:login'

# 2. URL a la que va el usuario una vez se loguea correctamente
LOGIN_REDIRECT_URL = 'core:dashboard'

# 3. URL a la que va el usuario tras cerrar sesión
LOGOUT_REDIRECT_URL = '/'

# Configuración de Keycloak
OIDC_RP_CLIENT_ID = os.environ.get('OIDC_RP_CLIENT_ID', 'sigeth')
OIDC_RP_CLIENT_SECRET = os.environ.get('OIDC_RP_CLIENT_SECRET', 'Eam6NXFg92AUIdxtYsihsAVRxKHkfgsT')
OIDC_RP_SIGN_ALGO = 'RS256'
# Configuración del cliente administrador de Keycloak (Service Account)
KEYCLOAK_ADMIN_CLIENT_ID = OIDC_RP_CLIENT_ID
KEYCLOAK_ADMIN_CLIENT_SECRET = OIDC_RP_CLIENT_SECRET

KEYCLOAK_URL = os.environ.get('KEYCLOAK_URL', 'http://192.168.1.26:8080')
REALM = os.environ.get('KEYCLOAK_REALM', 'municipio')

OIDC_OP_AUTHORIZATION_ENDPOINT = f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/auth"
OIDC_OP_TOKEN_ENDPOINT = f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/token"
OIDC_OP_USER_ENDPOINT = f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/userinfo"
OIDC_OP_JWKS_ENDPOINT = f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/certs"
OIDC_OP_LOGOUT_ENDPOINT = f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/logout"

# --- SINGLE LOGOUT (RP-Initiated Logout) ---
# Sin esto, mozilla-django-oidc SOLO destruye la sesión local de Django y
# nunca notifica a Keycloak. La sesión del IdP sigue viva y en el próximo
# request Keycloak vuelve a autenticar automáticamente (el loop reportado).

# 1. Necesario para poder armar el 'id_token_hint' que Keycloak exige
#    en el endpoint de logout (por defecto NO se guarda el id_token).
OIDC_STORE_ID_TOKEN = True

# 2. Punto de extensión oficial de la librería: función (request) -> str
#    que construye la URL real de logout contra Keycloak. Se ejecuta
#    ANTES de que OIDCLogoutView llame a auth.logout(request), así que
#    el id_token todavía está disponible en la sesión.
OIDC_OP_LOGOUT_URL_METHOD = 'core.auth.provider_logout'
OIDC_OP_RESET_CREDENTIALS_URL = f"{KEYCLOAK_URL}/realms/{REALM}/login-actions/reset-credentials?client_id={OIDC_RP_CLIENT_ID}"
