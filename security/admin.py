from django.contrib import admin
from .models import *

admin.site.register(BlockedIP)
admin.site.register(SuspiciousIP)