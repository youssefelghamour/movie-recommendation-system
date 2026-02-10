from datetime import datetime
from django.http import HttpResponseForbidden
from django.core.cache import cache
from .models import BlockedIP
import logging


# File logger
logger = logging.getLogger(__name__)
if not logger.handlers:
    fh = logging.FileHandler('requests.log')
    fh.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(fh)
    logger.setLevel(logging.INFO)


class SecurityMiddleware:
    """A middleware that logs each user’s requests to a file, including:
        - The timestamp
        - The user
        - The request path
        It also checks if the user's IP address is in a blocked list and denies access if it is
        and tracks requests per IP in Redis for anomaly detection
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ip = self.get_client_ip(request)
        path = request.path

        # Check if IP is blocked
        if BlockedIP.objects.filter(ip_address=ip).exists():
            return HttpResponseForbidden("Your IP has been blocked.")

        # Log request to file
        user = request.user if request.user.is_authenticated else 'Anonymous'
        logger.info(f"{datetime.now()} - User: {user} - IP: {ip} - Path: {path}")

        # Redis tracking: store timestamps of requests per IP
        key = f"requests:{ip}"
        now = datetime.utcnow().timestamp()
        timestamps = cache.get(key, [])
        # Filter out requests made more than an hour ago
        timestamps = [ts for ts in timestamps if ts > now - 3600]
        # Add current request timestamp
        timestamps.append(now)
        cache.set(key, timestamps, timeout=3600)

        response = self.get_response(request)
        return response

    def get_client_ip(self, request):
        """ Retrieve the client's IP address from the request """
        # Check for X-Forwarded-For header first (in case of proxy in production)
        # x_forwarded_for will look like: "client_ip, proxy1_ip, proxy2_ip"
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')

        if x_forwarded_for:  # In production, behind a proxy
            ip = x_forwarded_for.split(',')[0]
        else:  # Direct request in local development
            ip = request.META.get('REMOTE_ADDR')
        return ip
