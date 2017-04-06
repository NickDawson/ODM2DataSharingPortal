"""
Django settings for WebSDL project.

Generated by 'django-admin startproject' using Django 1.9.3.

For more information on this file, see
https://docs.djangoproject.com/en/1.9/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.9/ref/settings/
"""

import os
import json

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Loads settings configuration data from settings.json file
data = {}
try:
    with open(os.path.join(BASE_DIR, 'settings', 'settings.json')) as data_file:
        data = json.load(data_file)
except IOError:
    print("You need to setup the settings data file (see instructions in base.py file.)")


# SECURITY WARNING: keep the secret key used in production secret!
try:
    SECRET_KEY = data["secret_key"]
except KeyError:
    print("The secret key is required in the settings.json file.")
    exit(1)

ALLOWED_HOSTS = []


# Application definition

INSTALLED_APPS = [
    'rest_framework',
    'dataloader',
    'dataloaderservices',
    'dataloaderinterface',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'widget_tweaks'
]

MIDDLEWARE_CLASSES = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.auth.middleware.SessionAuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
REST_FRAMEWORK = {
   'DEFAULT_RENDERER_CLASSES': (
       'rest_framework.renderers.JSONRenderer',
       'rest_framework.renderers.BrowsableAPIRenderer',
#       'rest_framework.renderers.AdminRenderer',
   )
}

ROOT_URLCONF = 'WebSDL.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')]
        ,
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

WSGI_APPLICATION = 'WebSDL.wsgi.application'


# Database
# https://docs.djangoproject.com/en/1.9/ref/settings/#databases

DATABASES = {}
for database in data['databases']:
    DATABASES[database['name']] = {
        'ENGINE': database['engine'],
        'NAME': database['schema'],
        'USER': database['user'] if 'user' in database else '',
        'PASSWORD': database['password'] if 'password' in database else '',
        'HOST': database['host'] if 'host' in database else '',
        'PORT': database['port'] if 'port' in database else '',
        'OPTIONS': database['options'] if 'options' in database else {},
        'TEST': database['test'] if 'test' in database else {},
    }

# Password validation
# https://docs.djangoproject.com/en/1.9/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    # {
    #     'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    # },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    # {
    #     'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    # },
]


# Internationalization
# https://docs.djangoproject.com/en/1.9/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True

LOGIN_URL = 'login'

DATABASE_ROUTERS = ['WebSDL.db_routers.WebSDLRouter']


# Security and SSL
#
# SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
#
# SECURE_SSL_REDIRECT = True

RECAPTCHA_KEY = data["recaptcha_secret_key"] if "recaptcha_secret_key" in data else ""

RECAPTCHA_USER_KEY = data["recaptcha_user_key"] if "recaptcha_user_key" in data else ""

RECAPTCHA_VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"
