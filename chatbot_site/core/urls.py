from django.urls import path

from . import views

urlpatterns = [
    # System choice entry point
    path('', views.system_choice, name='system_choice'),
    
    # Human-AI deliberation
    path('human/', views.entry_point, name='entry'),
    path('human/moderator/', views.moderator_dashboard, name='moderator_dashboard'),
    path('api/create-session/', views.create_new_session_api, name='create_new_session_api'),
    path('api/generate-questions/', views.generate_questions_api, name='generate_questions_api'),
    path('human/user/<int:user_id>/', views.user_conversation, name='user_conversation'),
    
    # AI-AI deliberation
    path('ai/', views.ai_entry_point, name='ai_entry'),
    path('ai/moderator/', views.ai_moderator_dashboard, name='ai_moderator_dashboard'),
    path('ai/results/<int:run_id>/', views.ai_deliberation_results, name='ai_deliberation_results'),
    # Grader flow
    path('grader/', views.grader_entry_point, name='grader_entry'),
    path('grader/moderator/', views.grader_moderator_dashboard, name='grader_moderator_dashboard'),
    path('grader/user/<int:user_id>/', views.grader_user_view, name='grader_user'),
    path('grader/export/<int:session_id>/', views.grader_export_csv, name='grader_export'),
    # Integrated grader for DiscussionSession (legacy)
    path('human/grader/user/<int:user_id>/', views.discussion_grader_user_view, name='discussion_grader_user'),
    path('human/grader/export/<int:session_id>/', views.discussion_grader_export_csv, name='discussion_grader_export'),
    # Unified export views (new format)
    path('human/export/user/<int:session_id>/<int:user_id>/', views.export_user_csv, name='export_user_csv'),
    path('human/export/ratings/<int:session_id>/', views.export_ratings_csv, name='export_ratings_csv'),
    path('human/export/summary/<int:session_id>/', views.download_summary_json, name='download_summary_json'),
]

