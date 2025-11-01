from django.contrib import admin

from .models import DiscussionSession, UserConversation, AIDeliberationSession, AIDebateRun, AIDebateSummary


@admin.register(DiscussionSession)
class DiscussionSessionAdmin(admin.ModelAdmin):
    list_display = ("s_id", "topic", "is_active", "rag_chunk_count", "created_at")
    list_filter = ("is_active", "created_at")
    fields = (
        "s_id",
        "topic",
        "description",
        "knowledge_base",
        "user_system_prompt",
        "moderator_system_prompt",
    )
    list_filter = ("is_active",)
    search_fields = ("s_id", "topic")
    readonly_fields = ("rag_chunk_count", "rag_last_built_at", "created_at", "updated_at")


@admin.register(UserConversation)
class UserConversationAdmin(admin.ModelAdmin):
    list_display = (
        "session",
        "user_id",
        "message_count",
        "consecutive_no_new",
        "active",
        "updated_at",
    )
    search_fields = ("user_id", "session__s_id")
    list_filter = ("active",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(AIDeliberationSession)
class AIDeliberationSessionAdmin(admin.ModelAdmin):
    list_display = ("s_id", "topic", "is_active", "created_at")
    list_filter = ("is_active", "created_at")
    fields = (
        "s_id",
        "topic",
        "description",
        "objective_questions",
        "personas",
        "system_prompt_template",
    )
    search_fields = ("s_id", "topic")
    readonly_fields = ("created_at", "updated_at")


@admin.register(AIDebateRun)
class AIDebateRunAdmin(admin.ModelAdmin):
    list_display = ("session", "completed", "created_at")
    list_filter = ("completed", "created_at")
    search_fields = ("session__s_id",)
    readonly_fields = ("created_at", "updated_at", "transcript")


@admin.register(AIDebateSummary)
class AIDebateSummaryAdmin(admin.ModelAdmin):
    list_display = ("session", "created_at")
    search_fields = ("session__s_id", "topic")
    readonly_fields = ("created_at", "updated_at")

