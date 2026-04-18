from django.urls import path
from organizations import views

urlpatterns = [
    path('<slug:slug>/theme/',                  views.get_organization_theme,    name='organization_theme'),
    path('<int:org_id>/members/',               views.get_members,               name='get_members'),
    path('<int:org_id>/members/add/',           views.manage_members,            name='manage_members'),
    path('<int:org_id>/members/<int:user_id>/', views.remove_member,             name='remove_member'),
    path('<int:org_id>/service-members/',       views.manage_service_members,    name='service_members'),
    path('<int:org_id>/services/',              views.get_services,              name='get_services'),
    path('<int:org_id>/services/add/',          views.add_service,               name='add_service'),
]