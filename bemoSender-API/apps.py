from django.apps import AppConfig
from django.conf import settings
from loguru import logger



class bemoSenderrConfig(AppConfig):
    name = 'bemoSenderr'
    verbose_name = 'bemoSenderr'


    def ready(self):
        import bemoSenderr.signals  # noqa
        # This will make sure the app is always imported when
        # Django starts so that shared_task will use this app.
        # noinspection PyUnresolvedReferences
        """
        In this function we get or create the Update-Rates, Authorize-Deposits and Check-Deposits Celery periodic tasks.
        # This is a hack by not adding them manually (stable hack)
        """
        from .celery import app as celery_app
        import bemoSenderr.signals
        __all__ = ('celery_app',)
        from bemoSenderr.models.task import PeriodicTasksEntry

        from redbeat import RedBeatSchedulerEntry as Entry
        from .celery import app
        if settings.CONFIG and settings.CONFIG.get('env', None) in ['Dev-V3', None]:
            env = "Dev-V3"
        else:
            env = "Prod-V3"
        logger.info(f"GLOBAL PERIODIC TASKS ENVIRONMENT {env}")
        deposits_schedule = 900
        if env == "Prod-V3":
            deposits_schedule = 600
        try:
            e = Entry.from_key(key=f'redbeat:Update Rates periodic task', app=app)
            update_rates_instance = PeriodicTasksEntry.objects.filter(key=e.key).first()
            if not update_rates_instance:
                periodic_task, created = PeriodicTasksEntry.objects.get_or_create(key=e.key, task="bemoSenderr.tasks.update_rates", 
                        name=e.name, schedule=900, args=None
                )

        except Exception as e:
            print('Update Rates periodic task doesnt exist !', e.args)
            e = Entry(schedule=900, name=f'Update Rates periodic task', app=app,
                        task="bemoSenderr.tasks.update_rates")
            e.save()
            key = e.key
            # Periodic task object to manage redbeat periodic tasks dynamically
            periodic_task, created = PeriodicTasksEntry.objects.get_or_create(key=key, task="bemoSenderr.tasks.update_rates", 
                    name=e.name, schedule=900, args=None
            )

        try:
            e = Entry.from_key(key=f'redbeat:Authorize Deposits Periodic Task', app=app)
            authorize_deposits_instance = PeriodicTasksEntry.objects.filter(key=e.key).first()
            if not authorize_deposits_instance:
                periodic_task, created = PeriodicTasksEntry.objects.get_or_create(key=e.key, task="bemoSenderr.tasks.authorize_deposits", 
                        name=e.name, schedule=deposits_schedule, args=None
                )
        except Exception as e:
            print('Authorize Deposits periodic task doesnt exist ! ', e.args)
            e = Entry(schedule=deposits_schedule, name=f'Authorize Deposits Periodic Task', app=app,
                        task="bemoSenderr.tasks.authorize_deposits")
            e.save()
            key = e.key
            print(e.key)
            # Periodic task object to manage redbeat periodic tasks dynamically
            periodic_task, created = PeriodicTasksEntry.objects.get_or_create(key=key, task="bemoSenderr.tasks.authorize_deposits", 
                    name=e.name, schedule=deposits_schedule, args=None
            )
        
        try:
            e = Entry.from_key(key=f'redbeat:Check Deposits Periodic Task', app=app)
            check_deposits_instance = PeriodicTasksEntry.objects.filter(key=e.key).first()
            if not check_deposits_instance:
                periodic_task, created = PeriodicTasksEntry.objects.get_or_create(key=e.key, task="bemoSenderr.tasks.check_deposits", 
                        name=e.name, schedule=deposits_schedule, args=None
                )
        except Exception as e:
            print('Check Deposits periodic task doesnt exist !', e.args)
            e = Entry(schedule=deposits_schedule, name=f'Check Deposits Periodic Task', app=app,
                        task="bemoSenderr.tasks.check_deposits")
            e.save()
            key = e.key
            print(e.key)
            # Periodic task object to manage redbeat periodic tasks dynamically
            periodic_task, created = PeriodicTasksEntry.objects.get_or_create(key=key, task="bemoSenderr.tasks.check_deposits", 
                    name=e.name, schedule=deposits_schedule, args=None
            )
        try:
            e = Entry.from_key(key=f'redbeat:Check Refunds Periodic Task', app=app)
            check_refunds_instance = PeriodicTasksEntry.objects.filter(key=e.key).first()
            if not check_refunds_instance:
                periodic_task, created = PeriodicTasksEntry.objects.get_or_create(key=e.key, task="bemoSenderr.tasks.check_refunds", 
                        name=e.name, schedule=deposits_schedule, args=None
                )
        except Exception as e:
            print('Check Refunds periodic task doesnt exist !', e.args)
            e = Entry(schedule=deposits_schedule, name=f'Check Refunds Periodic Task', app=app,
                        task="bemoSenderr.tasks.check_refunds")
            e.save()
            key = e.key
            print(e.key)
            # Periodic task object to manage redbeat periodic tasks dynamically
            periodic_task, created = PeriodicTasksEntry.objects.get_or_create(key=key, task="bemoSenderr.tasks.check_refunds", 
                    name=e.name, schedule=deposits_schedule, args=None
            )
        try:
            e = Entry.from_key(key=f'redbeat:Check Async Flinks Requests', app=app)
            check_flinks_instance = PeriodicTasksEntry.objects.filter(key=e.key).first()
            if not check_flinks_instance:
                periodic_task, created = PeriodicTasksEntry.objects.get_or_create(key=e.key, task="bemoSenderr.tasks.check_refunds", 
                        name=e.name, schedule=60, args=None
                )
        except Exception as e:
            print('Check Async Flinks Requests periodic task doesnt exist !', e.args)
            e = Entry(schedule=60, name=f'Check Async Flinks Requests', app=app,
                        task="bemoSenderr.tasks.update_pending_sign_up_flinks")
            e.save()
            key = e.key
            print(e.key)
            # Periodic task object to manage redbeat periodic tasks dynamically
            periodic_task, created = PeriodicTasksEntry.objects.get_or_create(key=key, task="bemoSenderr.tasks.update_pending_sign_up_flinks", 
                    name=e.name, schedule=60, args=None
            )


