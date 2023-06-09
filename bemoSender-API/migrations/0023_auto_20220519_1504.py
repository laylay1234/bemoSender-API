# Generated by Django 3.2.8 on 2022-05-19 14:04

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('bemosenderrr', '0022_auto_20220518_1959'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='user',
            name='device_token',
        ),
        migrations.CreateModel(
            name='UserToken',
            fields=[
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, help_text='Autogenerated UUID.', primary_key=True, serialize=False, unique=True, verbose_name='Internal UUID')),
                ('created_at', models.DateTimeField(auto_now_add=True, help_text='Timestamp automatically generated upon creation of the object.', verbose_name='Created at')),
                ('updated_at', models.DateTimeField(auto_now=True, help_text='Automatically updated to the last modification timestamp.', verbose_name='Updated at')),
                ('_version', models.CharField(blank=True, help_text='Datatstore version used in mutations', max_length=255, null=True)),
                ('device_token', models.CharField(help_text='The device token', max_length=255)),
                ('device_type', models.CharField(help_text='The device type', max_length=255)),
                ('app_version', models.CharField(help_text='The App version', max_length=255)),
                ('time_zone', models.CharField(help_text='The timezone of the user', max_length=255)),
                ('gcm_senderrid', models.CharField(blank=True, help_text='The GCM senderrID', max_length=255, null=True)),
                ('device_data', models.JSONField(blank=True, default=dict, help_text='The device data', null=True)),
                ('app_identifier', models.CharField(blank=True, help_text='The app identifier', max_length=255, null=True)),
                ('installation_id', models.CharField(blank=True, help_text='The installation id', max_length=255, null=True)),
                ('user', models.ForeignKey(blank=True, help_text='The associated user', null=True, on_delete=django.db.models.deletion.RESTRICT, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['updated_at'],
                'abstract': False,
            },
        ),
    ]
