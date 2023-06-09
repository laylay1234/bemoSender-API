# Generated by Django 3.2.8 on 2022-04-05 17:52

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('bemoSenderr', '0015_auto_20220404_2027'),
    ]

    operations = [
        migrations.CreateModel(
            name='AppSettings',
            fields=[
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, help_text='Autogenerated UUID.', primary_key=True, serialize=False, unique=True, verbose_name='Internal UUID')),
                ('created_at', models.DateTimeField(auto_now_add=True, help_text='Timestamp automatically generated upon creation of the object.', verbose_name='Created at')),
                ('updated_at', models.DateTimeField(auto_now=True, help_text='Automatically updated to the last modification timestamp.', verbose_name='Updated at')),
                ('_version', models.CharField(blank=True, help_text='Datatstore version used in mutations', max_length=255, null=True)),
                ('clientHelpDesk', models.JSONField(blank=True, help_text='Client support information', null=True)),
                ('policyUrlList', models.JSONField(blank=True, help_text='Used in the frontend to display the desired link to TOS and privacy policies based on mobile app language and origin country.', null=True)),
                ('minTransactionValue', models.JSONField(blank=True, help_text='Minimum transaction values for each origin country', null=True)),
                ('rateLimits', models.JSONField(blank=True, help_text='Used in the admin back-office to validate the values entered when creating/updating ExchangeRates and ExchangeRateTiers', null=True)),
                ('rateTierLevels', models.JSONField(blank=True, help_text='Used by the backend as default values when creating ExchangeRateTiers', null=True)),
            ],
            options={
                'verbose_name_plural': 'App Settings',
                'ordering': ['created_at'],
            },
        ),
        migrations.AlterField(
            model_name='usertier',
            name='monthly_max',
            field=models.JSONField(help_text='The maximum number of transactions and amount per month'),
        ),
        migrations.AlterField(
            model_name='usertier',
            name='quarterly_max',
            field=models.JSONField(help_text='The maximum number of transactions and amount per 3 months'),
        ),
        migrations.AlterField(
            model_name='usertier',
            name='tx_max',
            field=models.JSONField(help_text='the maximum amount to send in a transaction for this level'),
        ),
        migrations.AlterField(
            model_name='usertier',
            name='yearly_max',
            field=models.JSONField(help_text='The maximum number of transactions and amount per year'),
        ),
    ]
