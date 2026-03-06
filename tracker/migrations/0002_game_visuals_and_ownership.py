from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tracker", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="gamerecord",
            name="cover_url",
            field=models.URLField(blank=True),
        ),
        migrations.AddField(
            model_name="gamerecord",
            name="logo_url",
            field=models.URLField(blank=True),
        ),
        migrations.AddField(
            model_name="gamerecord",
            name="ownership_type",
            field=models.CharField(
                choices=[
                    ("OWNED", "Propio"),
                    ("RECENT_ONLY", "Reciente (posible préstamo)"),
                    ("MANUAL", "Manual"),
                ],
                default="MANUAL",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="gamerecord",
            name="recent_minutes",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="gamerecord",
            name="store_url",
            field=models.URLField(blank=True),
        ),
    ]
