"""ASGI config for the Kilo Gateway dashboard project."""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kilo_dashboard.settings")

application = get_asgi_application()
