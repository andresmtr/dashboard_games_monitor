from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tracker", "0003_external_account_token"),
    ]

    operations = [
        migrations.AddField(
            model_name="gamerecord",
            name="estimated_price",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
    ]
