from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tracker", "0002_game_visuals_and_ownership"),
    ]

    operations = [
        migrations.CreateModel(
            name="ExternalAccountToken",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider", models.CharField(choices=[("GOG", "GOG")], max_length=20, unique=True)),
                ("access_token", models.TextField(blank=True)),
                ("refresh_token", models.TextField(blank=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("external_user_id", models.CharField(blank=True, max_length=120)),
                ("account_name", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["provider"]},
        ),
    ]
