from django.urls import path
from accounts import views

urlpatterns = [
    path('register/', views.register,      name='register'),
    path('login/',    views.login_view,    name='login'),
    path('refresh/',  views.refresh_token, name='refresh_token'),
    path('me/',       views.me,            name='me'),
]