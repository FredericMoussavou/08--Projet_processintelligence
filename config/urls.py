from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/procedures/', include('procedures.urls')),
    path('api/organizations/', include('organizations.urls')),
]