from django.contrib import admin

from .models import DiscussionSession, UserConversation


@admin.register(DiscussionSession)
class DiscussionSessionAdmin(admin.ModelAdmin):
    list_display = ("s_id", "topic", "is_active", "rag_chunk_count", "created_at")
    list_filter = ("is_active", "created_at")
    fields = (
        "s_id",
        "topic",
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
