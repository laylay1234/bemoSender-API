# Generated by Django 3.2.8 on 2022-04-26 16:39

from django.db import migrations, models
import django_fsm


class Migration(migrations.Migration):

    dependencies = [
        ('bemosenderrr', '0016_auto_20220405_1852'),
    ]

    operations = [
        migrations.AlterField(
            model_name='collecttransaction',
            name='status',
            field=models.CharField(choices=[('NEW', 'New'), ('SUCCESS', 'Transaction successfully collected'), ('AML_BLOCKED', 'Money laundering suspected !'), ('BLOCKED', 'Transaction blocked'), ('NOT_FOUND', 'Transaction not found'), ('CANCELLED', 'Transaction cancelled'), ('ERROR', 'Transaction error'), ('ON_HOLD', 'Transaction on hold'), ('IN_PROGRESS', 'Transaction in progress'), ('REFUNDED', 'Transaction refunded'), ('REJECTED', 'Transaction rejected '), ('COLLECT_READY', 'Transaction ready to be collected')], max_length=255),
        ),
        migrations.AlterField(
            model_name='globaltransaction',
            name='status',
            field=django_fsm.FSMField(choices=[('NEW', 'New'), ('FUNDTRANSACTION_IN_PROGRESS', 'Fund transaction in progress'), ('COLLECTTRANSACTION_IN_PROGRESS', 'Collect transaction in progress'), ('REFUNDED', 'Transaction refunded'), ('REFUNDTRANSACTION_IN_PROGRESS', 'Refund transaction in progress'), ('SUCCESS', 'Transaction completed successfully'), ('CANCELLED', 'Transaction cancelled'), ('BLOCKED', 'Collect transactions blocked'), ('FUNDING_ERROR', 'Funding transaction error'), ('NOT_FOUND', 'Transaction not found'), ('REFUNDED_ERROR', 'Refund Error')], default='NEW', help_text='Global Transaction status', max_length=64, verbose_name='Status'),
        ),
    ]
