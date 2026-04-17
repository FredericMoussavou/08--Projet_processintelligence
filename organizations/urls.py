from django.urls import path
from organizations import views

urlpatterns = [
    path('<slug:slug>/theme/', views.get_organization_theme, name='organization_theme'),
]