import threading

from django.apps import AppConfig


class DashboardConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "dashboard"

    def ready(self):
        # Pre-warm the upstream model cache in the background so the first
        # request after startup doesn't block on the API. fetch_models_from_api
        # swallows failures (returns an empty result) and the daemon thread
        # won't keep the process alive.
        from .views import fetch_models_from_api

        threading.Thread(target=fetch_models_from_api, daemon=True).start()
