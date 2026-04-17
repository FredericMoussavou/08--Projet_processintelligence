from django.urls import path
from procedures import views

urlpatterns = [
    path('ingest/', views.ingest_procedure, name='ingest_procedure'),
    path('<int:procedure_id>/analyze/', views.analyze, name='analyze_procedure'),
]