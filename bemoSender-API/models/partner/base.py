from abc import abstractmethod

from celery import shared_task
from django.db import models
from django.utils.translation import ugettext_lazy as _
from bemoSenderr.models.base import AbstractBaseModel
from ..base import VerificationStatus


class VerificationTypes(models.TextChoices):
    kyc = 'KYC', _('KYC Verification')
    bank_verification = 'BANK_VERIFICATION', _('Bank Verification')


class AbstractPartnerTransaction(AbstractBaseModel):
    
    partner = models.ForeignKey('Partner', on_delete=models.RESTRICT)
    partner_response = models.JSONField(_('Partner API response'), null=True, blank=True)
    partner_response_formatted = models.JSONField(_('Contains specific element from the partner response in a format that we expect'), null=True, blank=True)
    
    def init(self):
        pass

    def reconciliation(self):
        pass

    @shared_task(bind=True)
    def ping(self):
        pass

    class Meta:
        abstract = True
        ordering = ['-updated_at']


class AbstractFundingPartner():
    @abstractmethod
    def fund(self):
        pass

    @abstractmethod
    def refund(self):
        pass

    @abstractmethod
    def check_status(self):
        pass

    @abstractmethod
    def cancel(self):
        pass


class AbstractCollectPartner():
    @abstractmethod
    def collect(self):
        pass

    @abstractmethod
    def check_status(self):
        pass

    @abstractmethod
    def cancel(self):
        pass


class AbstractConversionPartner():
    @abstractmethod
    def get_rates(self):
        pass


class AbstractVerificationRequest(AbstractBaseModel):
    user = models.ForeignKey('User', on_delete=models.RESTRICT, null=True, blank=True)
    status = models.CharField(_('Status'), max_length=255, choices=VerificationStatus.choices, null=True, blank=True)
    partner = models.ForeignKey('Partner', on_delete=models.RESTRICT, null=True, blank=True)
    user_snapshot = models.JSONField(_('User data'))
    partner_response = models.JSONField(_('Partner API response'), null=True, blank=True)

    def init(self):
        pass

    def reconciliation(self):
        pass

    @shared_task(bind=True)
    def ping(self):
        pass

    @abstractmethod
    def verify(self):
        pass
    
    def __str__(self) -> str:
        if self.user:
            return self.user.email
        else:
            return ""
    class Meta:
        abstract = True
        ordering = ['-updated_at']



class PartnerApiCallType(models.TextChoices):
    outbound = 'OUTBOUND', _('Outbound API call')
    inbound = 'INBOUND', _('Inbound API call')







