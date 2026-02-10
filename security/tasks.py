from celery import shared_task
from django.core.cache import cache
from .models import SuspiciousIP


# Thresholds
MAX_REQUESTS_PER_HOUR = 30000


@shared_task
def detect_anomalies():
    """Celery task to detect and to flag suspicious IPs:
        - High volume (>100 requests/hour)
        - Access to sensitive paths (/admin, /login)
    """
    # Get all keys in Redis that start with 'requests:'
    for key in cache.keys("requests:*"):
        ip = key.split(":")[1]
        timestamps = cache.get(key, [])

        ##### 1. Flag high volume

        # Check if the number of requests in the last hour exceeds the threshold for this IP
        if len(timestamps) > MAX_REQUESTS_PER_HOUR:
            SuspiciousIP.objects.get_or_create(
                ip_address=ip,
                reason="Request volume > 30000/hr"
            )
