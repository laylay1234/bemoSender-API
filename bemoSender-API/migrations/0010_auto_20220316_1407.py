# Generated by Django 3.2.8 on 2022-03-16 13:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bemosenderrr', '0009_alter_user_phone_number'),
    ]

    operations = [
        migrations.AddField(
            model_name='collecttransaction',
            name='partner_settlement_acc_snapshot',
            field=models.JSONField(blank=True, help_text='The currency and the account number of the partner settlement account', null=True),
        ),
        migrations.AlterField(
            model_name='country',
            name='calling_code',
            field=models.CharField(help_text='Country phone code', max_length=4),
        ),
        migrations.AlterField(
            model_name='globaltransaction',
            name='collect_method',
            field=models.CharField(max_length=255, verbose_name='Collect method of the user'),
        ),
    ]
