# Generated by Django 2.0.3 on 2018-04-07 13:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main_app', '0003_auto_20180329_0247'),
    ]

    operations = [
        migrations.AddField(
            model_name='query',
            name='satisfaction_link_is_alive',
            field=models.BooleanField(default=False),
        ),
    ]
