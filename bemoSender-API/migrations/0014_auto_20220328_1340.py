# Generated by Django 3.2.8 on 2022-03-28 12:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bemosenderrr', '0013_auto_20220322_1151'),
    ]

    operations = [
        migrations.AlterField(
            model_name='collecttransaction',
            name='status',
            field=models.CharField(choices=[('NEW', 'New'), ('SUCCESS', 'Transaction successful'), ('AML_BLOCKED', 'Money laundering suspected !'), ('BLOCKED', 'Transaction blocked'), ('NOT_FOUND', 'Transaction not found'), ('CANCELLED', 'Transaction cancelled'), ('ERROR', 'Transaction error'), ('ON_HOLD', 'Transaction on hold'), ('IN_PROGRESS', 'Transaction in progress'), ('REFUNDED', 'Transaction refunded')], max_length=255),
        ),
        migrations.AlterField(
            model_name='fundingtransaction',
            name='status',
            field=models.CharField(choices=[('IN_PROGRESS', 'Transaction in progress'), ('AUTH_ERROR', 'Authorization error'), ('COMPLETE_ERROR', 'Completion error'), ('ERROR', 'Transaction error'), ('FUNDED', 'Transaction successful')], max_length=255),
        ),
        migrations.AlterField(
            model_name='globaltransaction',
            name='status',
            field=models.CharField(choices=[('NEW', 'New'), ('FUNDTRANSACTION_IN_PROGRESS', 'Fund transaction in progress'), ('COLLECTTRANSACTION_IN_PROGRESS', 'Collect transaction in progress'), ('REFUNDTRANSACTION_IN_PROGRESS', 'Refund transaction in progress'), ('SUCCESS', 'Transaction completed successfully'), ('CANCELLED', 'Transaction cancelled'), ('AML_BLOCKED', 'Money laundering suspected !'), ('BLOCKED', 'Collect transactions blocked'), ('COLLECT_ERROR', 'Funding transaction error'), ('COLLECT_ON_HOLD', 'Collect transactions on hold'), ('FUNDING_ERROR', 'Collect transaction error'), ('NOT_FOUND', 'Transaction not found')], default='NEW', help_text='Global Transaction status', max_length=64, verbose_name='Status'),
        ),
    ]
