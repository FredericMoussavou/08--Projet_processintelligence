from django.urls import path
from procedures import views

urlpatterns = [
    path('ingest/', views.ingest_procedure, name='ingest_procedure'),
    path('<int:procedure_id>/analyze/', views.analyze, name='analyze_procedure'),
    path('<int:procedure_id>/export/pdf/', views.export_audit_pdf, name='export_audit_pdf'),
    path('<int:procedure_id>/export/bpmn/', views.export_bpmn, name='export_bpmn'),
    path('<int:procedure_id>/compliance/', views.check_compliance, name='check_compliance'),
    path('manual/<int:organization_id>/', views.export_manual, name='export_manual'),
    path('template/csv/', views.download_csv_template, name='csv_template'),
    path('rules/', views.list_rules, name='list_rules'),
    path('change-requests/', views.change_requests, name='change_requests'),
    path('change-requests/<int:cr_id>/', views.change_request_status, name='change_request_status'),
    path('change-requests/<int:cr_id>/approve/', views.approve_cr, name='approve_cr'),
    path('change-requests/<int:cr_id>/reject/', views.reject_cr, name='reject_cr'),
]