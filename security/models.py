from django.db import models


class BlockedIP(models.Model):
    """Model to store blocked IP addresses"""
    ip_address = models.GenericIPAddressField(unique=True)
    blocked_at = models.DateTimeField(auto_now_add=True)
    reason = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.ip_address


class SuspiciousIP(models.Model):
    """Model to store suspicious IP addresses with reasons"""
    ip_address = models.GenericIPAddressField()
    reason = models.CharField(max_length=255)
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)
    request_count = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.ip_address} - {self.reason}"