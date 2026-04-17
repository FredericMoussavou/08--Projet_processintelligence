from django.urls import path
from procedures import views

urlpatterns = [
    path('ingest/', views.ingest_procedure, name='ingest_procedure'),
    path('<int:procedure_id>/analyze/', views.analyze, name='analyze_procedure'),
    path('<int:procedure_id>/export/pdf/', views.export_audit_pdf, name='export_audit_pdf'),
    path('template/csv/', views.download_csv_template, name='csv_template'),
]