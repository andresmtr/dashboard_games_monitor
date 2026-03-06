from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="GameRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=255)),
                (
                    "platform",
                    models.CharField(
                        choices=[
                            ("STEAM", "Steam"),
                            ("PLAYSTATION", "PlayStation"),
                            ("XBOX", "Xbox"),
                            ("GOG", "GOG"),
                            ("EPIC", "Epic Games"),
                            ("NINTENDO", "Nintendo"),
                            ("OTHER", "Otro"),
                        ],
                        default="STEAM",
                        max_length=20,
                    ),
                ),
                ("genre", models.CharField(blank=True, max_length=120)),
                ("publisher", models.CharField(blank=True, max_length=120)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("BACKLOG", "Backlog"),
                            ("PLAYING", "Jugando"),
                            ("COMPLETED", "Completado"),
                            ("PAUSED", "Pausado"),
                            ("DROPPED", "Abandonado"),
                        ],
                        default="BACKLOG",
                        max_length=20,
                    ),
                ),
                ("purchase_price", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ("currency", models.CharField(default="USD", max_length=10)),
                ("purchase_date", models.DateField(blank=True, null=True)),
                ("imported_minutes", models.PositiveIntegerField(default=0)),
                ("manual_minutes", models.PositiveIntegerField(default=0)),
                ("achievements_total", models.PositiveIntegerField(default=0)),
                ("achievements_unlocked", models.PositiveIntegerField(default=0)),
                ("last_played_at", models.DateTimeField(blank=True, null=True)),
                ("external_id", models.CharField(blank=True, max_length=100)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["-last_played_at", "title"]},
        ),
        migrations.CreateModel(
            name="PlaySession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("started_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("ended_at", models.DateTimeField()),
                ("minutes", models.PositiveIntegerField(default=0, editable=False)),
                ("notes", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "game",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sessions",
                        to="tracker.gamerecord",
                    ),
                ),
            ],
            options={"ordering": ["-started_at"]},
        ),
    ]
