# Generated by Django 3.2.8 on 2022-03-17 16:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bemoSenderr', '0010_auto_20220316_1407'),
    ]

    operations = [
        migrations.AlterField(
            model_name='kycverificationrequest',
            name='custom_transaction_id',
            field=models.CharField(blank=True, help_text='An internally created transaction ID', max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='kycverificationrequest',
            name='partner_response',
            field=models.JSONField(null=True, verbose_name='Partner API response'),
        ),
        migrations.AlterField(
            model_name='kycverificationrequest',
            name='query_counter',
            field=models.CharField(blank=True, help_text='Current verification request counter', max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='userbankverificationrequest',
            name='partner_response',
            field=models.JSONField(null=True, verbose_name='Partner API response'),
        ),
    ]
