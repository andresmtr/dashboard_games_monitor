from django.db import migrations, models


def move_platforms_to_steam(apps, schema_editor):
    GameRecord = apps.get_model("tracker", "GameRecord")
    GameRecord.objects.exclude(platform="STEAM").update(platform="STEAM")


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):
    dependencies = [
        ("tracker", "0004_gamerecord_estimated_price"),
    ]

    operations = [
        migrations.RunPython(move_platforms_to_steam, noop_reverse),
        migrations.AlterField(
            model_name="gamerecord",
            name="platform",
            field=models.CharField(choices=[("STEAM", "Steam")], default="STEAM", max_length=20),
        ),
        migrations.DeleteModel(
            name="ExternalAccountToken",
        ),
    ]
