from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from django.utils import timezone


class GameRecord(models.Model):
    class Platform(models.TextChoices):
        STEAM = "STEAM", "Steam"

    class Status(models.TextChoices):
        BACKLOG = "BACKLOG", "Backlog"
        PLAYING = "PLAYING", "Jugando"
        COMPLETED = "COMPLETED", "Completado"
        PAUSED = "PAUSED", "Pausado"
        DROPPED = "DROPPED", "Abandonado"

    class OwnershipType(models.TextChoices):
        OWNED = "OWNED", "Propio"
        RECENT_ONLY = "RECENT_ONLY", "Reciente (posible préstamo)"
        MANUAL = "MANUAL", "Manual"

    title = models.CharField(max_length=255)
    platform = models.CharField(max_length=20, choices=Platform.choices, default=Platform.STEAM)
    genre = models.CharField(max_length=120, blank=True)
    publisher = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.BACKLOG)

    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    estimated_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=10, default=settings.APP_DEFAULT_CURRENCY)
    purchase_date = models.DateField(null=True, blank=True)

    imported_minutes = models.PositiveIntegerField(default=0)
    recent_minutes = models.PositiveIntegerField(default=0)
    manual_minutes = models.PositiveIntegerField(default=0)
    achievements_total = models.PositiveIntegerField(default=0)
    achievements_unlocked = models.PositiveIntegerField(default=0)
    last_played_at = models.DateTimeField(null=True, blank=True)
    ownership_type = models.CharField(max_length=20, choices=OwnershipType.choices, default=OwnershipType.MANUAL)

    external_id = models.CharField(max_length=100, blank=True)
    cover_url = models.URLField(blank=True)
    logo_url = models.URLField(blank=True)
    store_url = models.URLField(blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_played_at", "title"]

    def __str__(self) -> str:
        return f"{self.title} ({self.get_platform_display()})"

    def clean(self) -> None:
        if self.achievements_unlocked > self.achievements_total:
            raise ValidationError("Los logros desbloqueados no pueden superar el total.")

    @property
    def sessions_minutes(self) -> int:
        value = self.sessions.aggregate(total=Sum("minutes")).get("total")
        return int(value or 0)

    @property
    def total_tracked_minutes(self) -> int:
        return int(self.imported_minutes + self.manual_minutes + self.sessions_minutes)

    @property
    def total_hours(self) -> Decimal:
        return Decimal(self.total_tracked_minutes) / Decimal(60)


class PlaySession(models.Model):
    game = models.ForeignKey(GameRecord, on_delete=models.CASCADE, related_name="sessions")
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField()
    minutes = models.PositiveIntegerField(default=0, editable=False)
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self) -> str:
        return f"{self.game.title} - {self.minutes} min"

    def clean(self) -> None:
        if self.ended_at and self.started_at and self.ended_at < self.started_at:
            raise ValidationError("La fecha de fin no puede ser menor que la de inicio.")

    def save(self, *args, **kwargs):
        if self.started_at and self.ended_at:
            diff = self.ended_at - self.started_at
            self.minutes = max(int(diff.total_seconds() // 60), 0)
        super().save(*args, **kwargs)

        if self.ended_at and (self.game.last_played_at is None or self.ended_at > self.game.last_played_at):
            self.game.last_played_at = self.ended_at
            self.game.save(update_fields=["last_played_at", "updated_at"])
