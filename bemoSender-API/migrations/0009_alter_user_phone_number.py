# Generated by Django 3.2.8 on 2022-03-10 10:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bemosenderrr', '0008_user_phone_number'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='phone_number',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
