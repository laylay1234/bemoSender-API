from django.db import models
from django.utils.translation import ugettext_lazy as _
import uuid
from bemoSenderr.models.base import AbstractBaseModel
from bemoSenderr.types import STATUS_TYPES
from bemoSenderr.celery import app
from redbeat import RedBeatSchedulerEntry as Entry
from celery.schedules import schedule


class UserTask(AbstractBaseModel):
    task_id = models.UUIDField(_('Task ID'), unique=True, default=uuid.uuid4, help_text=_('Task ID.'))
    operation = models.CharField(max_length=255, blank=True, verbose_name=_('Operation Name'), help_text=_('The name of the operation.'))
    version = models.IntegerField(blank=True, verbose_name=_('Version'), help_text=_('Conflict management.'))
    arguments = models.JSONField(verbose_name=_('Arguments'), default=dict, blank=True, null=True, help_text=_('JSON object of arguments.'))
    results = models.JSONField(default=dict, blank=True, null=True, verbose_name=_('Results '), help_text=_('Results.'))
    status = models.CharField(_('UserTask Status'), max_length=16, choices=STATUS_TYPES, default='ACTIVE', help_text=_('You can soft delete objects by setting their status to deleted.'))

    def __str__(self):
        return "{0} - {1}".format(self.operation, self.task_id)

    class Meta:
        verbose_name = _('User Task')
        verbose_name_plural = _('User Tasks')
        ordering = ['operation']

class PeriodicTasksEntry(AbstractBaseModel):

    key = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    task = models.CharField(max_length=255, null=True, blank=True)
    enabled = models.BooleanField(default=True)
    schedule = models.IntegerField(default=10, help_text="The schedule in seconds.")
    args = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

    def get_entry(self):
        try:
            entry = Entry.from_key(self.key, app=app)
            return entry
        except Exception as e:
            print(e)
            return None

    def add_periodic_task(self, *args, **kwargs):
        try:
            entry = Entry.from_key(key=self.key)
            print('task already exists in redis')
        except Exception as e:
            print('task doesnt exist in redis')
            entry = Entry(name=self.name, task=self.task, args=self.args, schedule=self.schedule, app=app)
            entry.save()
            self.key = entry.key

    def delete_periodic_task(self):
        entry = self.get_entry()
        if entry:
            entry.delete()
    
    def update_task(self, *args, **kwargs):
        entry = Entry.from_key(self.key, app=app)
        entry.schedule = schedule(run_every=self.schedule)
        entry.save()
        print(entry)

    class Meta:
        verbose_name = _('Periodic Tasks Entry')
        verbose_name_plural = _('Periodic Tasks Entries')
        ordering = ['created_at']
