import os
from pathlib import Path
from decouple import config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Security and Settings via Decouple
SECRET_KEY = config('SECRET_KEY', default='django-insecure-j&makmw0@agvkr)9rcn)x=-2^p85r8jq7ov3sf7&z=#tsdc5l_')
DEBUG = config('DEBUG', default=True, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='*', cast=lambda v: [s.strip() for s in v.split(',')])

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # App do sistema
    'estoque',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'castock_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'castock_project.wsgi.application'

# Database Configuration with flexible SQLite Fallback and Auto-Creation
DB_NAME = config('DB_NAME', default='')
DB_USER = config('DB_USER', default='')
DB_PASSWORD = config('DB_PASSWORD', default='')
DB_HOST = config('DB_HOST', default='localhost')
DB_PORT = config('DB_PORT', default='5432')

def garantir_banco_postgres_existe(name, user, password, host, port):
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
    try:
        # Tenta conectar diretamente ao banco especificado
        conn = psycopg2.connect(
            dbname=name,
            user=user,
            password=password,
            host=host,
            port=port,
            connect_timeout=3
        )
        conn.close()
    except psycopg2.OperationalError as e:
        # Se falhar porque o banco de dados não existe, criamos automaticamente
        if "does not exist" in str(e) or "não existe" in str(e):
            try:
                # Conecta ao banco padrão 'postgres' para rodar a criação
                conn = psycopg2.connect(
                    dbname="postgres",
                    user=user,
                    password=password,
                    host=host,
                    port=port,
                    connect_timeout=3
                )
                conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
                cursor = conn.cursor()
                cursor.execute(f'CREATE DATABASE "{name}"')
                cursor.close()
                conn.close()
                print(f"\n[PostgreSQL] Banco de dados '{name}' criado automaticamente com sucesso!")
            except Exception as err:
                print(f"\n[PostgreSQL] Tentativa de criação automática do banco '{name}' falhou: {err}")
        else:
            print(f"\n[PostgreSQL] Erro de conexão (sem ser banco inexistente): {e}")

if DB_NAME and DB_USER:
    # Tenta criar o banco caso não exista antes do Django inicializar
    garantir_banco_postgres_existe(DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT)
    
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': DB_NAME,
            'USER': DB_USER,
            'PASSWORD': DB_PASSWORD,
            'HOST': DB_HOST,
            'PORT': DB_PORT,
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


# Custom User Model
AUTH_USER_MODEL = 'estoque.Usuario'

# Password Hashers - Prioridade máxima para Argon2
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
]

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Localization
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Configurações de Mídia para Upload de Fotos
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Session Expiration (30 minutos de inatividade)
SESSION_COOKIE_AGE = 1800  # 30 minutos em segundos
SESSION_SAVE_EVERY_REQUEST = True  # Atualiza o cookie a cada requisição para manter a sessão ativa durante uso

# URL de Autenticação e Redirecionamento (Evita Page Not Found 404)
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'

# Custom System Logging Configuration

LOGS_DIR = BASE_DIR / 'logs'
if not LOGS_DIR.exists():
    LOGS_DIR.mkdir()

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOGS_DIR / 'castock.log',
            'maxBytes': 1024 * 1024 * 5,  # 5 MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
        'estoque': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}
