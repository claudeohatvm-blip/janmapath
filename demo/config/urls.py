from django.urls import path

from web import views

urlpatterns = [
    path("", views.form, name="form"),
    path("generate", views.generate, name="generate"),
    path("generating/<str:job_id>", views.generating, name="generating"),
    path("stream/<str:job_id>", views.stream, name="stream"),
    path("report/<str:job_id>", views.report, name="report"),
    path("report/<str:job_id>/pdf", views.report_pdf, name="report_pdf"),
    path("api/chart/<str:job_id>", views.chart_json, name="chart_json"),
    path("setup/ai", views.setup_ai, name="setup_ai"),
]
