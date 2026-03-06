from django.contrib import admin

from tracker.models import GameRecord, PlaySession


@admin.register(GameRecord)
class GameRecordAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "platform",
        "ownership_type",
        "status",
        "purchase_price",
        "estimated_price",
        "currency",
        "last_played_at",
    )
    search_fields = ("title", "external_id", "publisher")
    list_filter = ("platform", "ownership_type", "status", "currency")


@admin.register(PlaySession)
class PlaySessionAdmin(admin.ModelAdmin):
    list_display = ("game", "started_at", "ended_at", "minutes")
    search_fields = ("game__title",)
