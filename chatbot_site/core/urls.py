from django.urls import path

from . import views

urlpatterns = [
    path('', views.entry_point, name='entry'),
    path('moderator/', views.moderator_dashboard, name='moderator_dashboard'),
    path('api/create-session/', views.create_new_session_api, name='create_new_session_api'),
    path('api/generate-questions/', views.generate_questions_api, name='generate_questions_api'),
    path('user/<int:user_id>/', views.user_conversation, name='user_conversation'),
]
