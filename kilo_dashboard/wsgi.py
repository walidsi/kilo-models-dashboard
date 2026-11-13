"""WSGI config for the Kilo Gateway dashboard project."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kilo_dashboard.settings")

application = get_wsgi_application()
