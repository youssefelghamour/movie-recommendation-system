import os
from celery import Celery

os.environ.setdefault(
    'DJANGO_SETTINGS_MODULE',
    'recommendation_system.settings'
)

app = Celery('recommendation_system')
# Read settings from Django settings, using CELERY_ prefix
app.config_from_object('django.conf:settings', namespace='CELERY')
# Auto-discover tasks in all installed apps
app.autodiscover_tasks()