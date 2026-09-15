from django.urls import path

from web import views

urlpatterns = [
    path("", views.form, name="form"),
    path("generate", views.generate, name="generate"),
    path("generating/<str:job_id>", views.generating, name="generating"),
    path("stream/<str:job_id>", views.stream, name="stream"),
    path("chart/<str:job_id>", views.chart, name="chart"),
    path("api/chart/<str:job_id>", views.chart_json, name="chart_json"),
]
