import os

# SEC-036: Debug mode on
DEBUG = True

# SEC-017: Hardcoded SECRET_KEY
SECRET_KEY = "django-insecure-super-secret-key-1234567890abcdef"

# SEC-039: ALLOWED_HOSTS allows all
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'myapp',
]

# SEC-023: Missing CsrfViewMiddleware
MIDDLEWARE = [
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
]

ROOT_URLCONF = 'myproject.urls'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'mydb',
        'USER': 'admin',
        'PASSWORD': 'supersecretpassword123',
        'HOST': 'prod-db.internal',
        'PORT': '5432',
    }
}
