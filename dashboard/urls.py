from django.urls import path

from . import views

urlpatterns = [
    path("", views.model_list, name="model_list"),
    path("api/models/", views.api_models, name="api_models"),
    path("api/models/<path:model_id>/", views.api_model_detail, name="api_model_detail"),
]
