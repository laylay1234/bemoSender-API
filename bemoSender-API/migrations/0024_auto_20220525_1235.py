# Generated by Django 3.2.8 on 2022-05-25 11:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bemoSenderr', '0023_auto_20220519_1504'),
    ]

    operations = [
        migrations.AlterField(
            model_name='exchangeratetier',
            name='collect_transaction_method_fees',
            field=models.JSONField(blank=True, help_text='Fees related to the delivery method', null=True),
        ),
    ]
