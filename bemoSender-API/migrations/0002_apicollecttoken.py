# Generated by Django 3.2.8 on 2022-02-22 17:31

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('bemoSenderr', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='APICollectToken',
            fields=[
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, help_text='Autogenerated UUID.', primary_key=True, serialize=False, unique=True, verbose_name='Internal UUID')),
                ('created_at', models.DateTimeField(auto_now_add=True, help_text='Timestamp automatically generated upon creation of the object.', verbose_name='Created at')),
                ('updated_at', models.DateTimeField(auto_now=True, help_text='Automatically updated to the last modification timestamp.', verbose_name='Updated at')),
                ('_version', models.CharField(blank=True, help_text='Datatstore version used in mutations', max_length=255, null=True)),
                ('token', models.CharField(help_text='The Partner API user generated token', max_length=255)),
                ('expires_at', models.DateTimeField(editable=False, help_text='Expiration time of the token')),
                ('api_user', models.ForeignKey(help_text='The associated API User', on_delete=django.db.models.deletion.RESTRICT, to=settings.AUTH_USER_MODEL)),
                ('global_transaction', models.ForeignKey(help_text='The global transaction associated', on_delete=django.db.models.deletion.RESTRICT, to='bemoSenderr.globaltransaction')),
            ],
            options={
                'ordering': ['updated_at'],
                'abstract': False,
            },
        ),
    ]