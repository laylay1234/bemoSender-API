# Generated by Django 3.2.8 on 2022-03-07 16:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bemosenderrr', '0006_apirequestmonitoring'),
    ]

    operations = [
        migrations.AlterField(
            model_name='globaltransaction',
            name='invoice_number',
            field=models.BigIntegerField(blank=True, null=True, verbose_name='The invoice number'),
        ),
    ]
