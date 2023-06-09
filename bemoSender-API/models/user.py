# from django.contrib.auth.base_user import AbstractUser
import json
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db.models.deletion import PROTECT
from django.forms import ValidationError
from guardian.mixins import GuardianUserMixin
from bemosenderrr import models
from django.db import models
from django.utils.translation import ugettext_lazy as _
from django_cryptography.fields import encrypt
from bemosenderrr.models.base import AbstractBaseModel, JSONWrappedTextField

import reversion


@reversion.register()
class User(AbstractBaseModel, AbstractUser, GuardianUserMixin):
    """
    Table contains cognito-users & django-users.

    PermissionsMixin leverage built-in django model permissions system
    (which allows to limit information for staff users via Groups).

    Note: Django-admin user and app user not split in different tables because of simplicity of development.
    Some libraries assume there is only one user model, and they can't work with both.
    For example to have a history log of changes for entities - to save which user made a change of object attribute,
    perhaps, auth-related libs, and some other.
    With current implementation we don't need to fork, adapt and maintain third party packages.
    They should work out of the box.
    The disadvantage is - cognito-users will have unused fields which always empty. Not critical.
    """
    username_validator = UnicodeUsernameValidator()

    ### Common fields ###
    # For cognito-users username will contain `sub` claim from jwt token
    # (unique identifier (UUID) for the authenticated user).
    # For django-users it will contain username which will be used to login into django-admin site
    # TODO do a migration to add custom_fields
    # For adding custom fields use this : object.custom_fields.create(key="some_key", value="some_value")
    # custom_fields = GenericRelation(CustomField, related_query_name='user', verbose_name=('Custom Fields'), help_text=('You can set custom fields for complex scenarios.'))
    ##user_data = models.JSONField(_('User Information'), default=dict)
    #protected_data = models.JSONField(_('User tier data '), editable=True, default={})
    #address_book = models.JSONField(_('Address book'), default={})
    #TODO validate this
    phone_number = models.CharField(max_length=255, null=True, blank=True)
    locale = models.CharField(max_length=6, help_text=_('User preferred language'), null=True, blank=True)
    description = models.CharField(max_length=255, help_text="A quick description of this user", null=True, blank=True)
    credentials = encrypt(JSONWrappedTextField(null=True, blank=True, default=None))

    USERNAME_FIELD = 'username'
    EMAIL_FIELD = 'email'
    REQUIRED_FIELDS = ['email']  # used only on createsuperuser
    @property
    def is_django_user(self):
        return self.has_usable_password()

    def __str__(self) -> str:
        return f'{self.email}'


class AdminAlerts(AbstractBaseModel):
    user = models.ForeignKey('User', help_text=_('The statff or admin user'), on_delete=models.RESTRICT)
    can_get_receiver_sms = models.BooleanField(help_text=_("Can receive sms notifications"))
    can_receive_admin_alerts = models.BooleanField(help_text=_("Can receive email alerts? (new transactions and paid transactions alerts)"))
    can_receive_celery_exceptions = models.BooleanField(help_text=_("Can receive celery email exceptions?"), default=False)

    def __str__(self) -> str:
        return self.user.email

    class Meta:
        verbose_name = _('Admin Alerts')
        verbose_name_plural = _('Admin Alerts')
        ordering = ['created_at']


class UserToken(AbstractBaseModel):

    user = models.ForeignKey('User', help_text=_('The associated user'), on_delete=models.RESTRICT, null=True, blank=True)
    device_token = models.CharField(max_length=255, help_text=_('The device token'))
    device_type = models.CharField(max_length=255, help_text=_('The device type'))
    app_version = models.CharField(max_length=255, help_text=_('The App version'))
    time_zone = models.CharField(max_length=255, help_text=_('The timezone of the user'))
    gcm_senderrid = models.CharField(max_length=255, help_text=_('The GCM senderrID'), null=True, blank=True)
    device_data = models.JSONField(help_text=_('The device data'), default=dict, null=True, blank=True)
    app_identifier = models.CharField(max_length=255, help_text=_('The app identifier'), null=True, blank=True)
    installation_id = models.CharField(max_length=255, help_text=_('The installation id'), null=True, blank=True)

    def __str__(self) -> str:
        return f"{str(self.device_type).upper()} {self.user.first_name} {self.user.last_name}"