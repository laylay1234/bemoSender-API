default_app_config = 'bemoSenderr.apps.bemoSenderrConfig'

from .celery import app as celery_app
__all__ = ('celery_app',)
