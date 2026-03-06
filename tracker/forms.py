from django import forms

from tracker.models import GameRecord, PlaySession


class GameRecordForm(forms.ModelForm):
    class Meta:
        model = GameRecord
        fields = [
            "title",
            "ownership_type",
            "genre",
            "publisher",
            "status",
            "purchase_price",
            "estimated_price",
            "currency",
            "purchase_date",
            "imported_minutes",
            "recent_minutes",
            "manual_minutes",
            "achievements_total",
            "achievements_unlocked",
            "last_played_at",
            "external_id",
            "cover_url",
            "logo_url",
            "store_url",
            "notes",
        ]
        widgets = {
            "purchase_date": forms.DateInput(attrs={"type": "date"}),
            "last_played_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }


class PlaySessionForm(forms.ModelForm):
    class Meta:
        model = PlaySession
        fields = ["started_at", "ended_at", "notes"]
        widgets = {
            "started_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "ended_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }
