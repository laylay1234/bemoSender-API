from celery import shared_task
import requests
from bemoSenderr.logger import send_email_celery_exception
from bemoSenderr.models.base import PartnerType
from bemoSenderr.models.partner.base import AbstractConversionPartner
from bemoSenderr.utils.log import debug
from django.apps import apps



class CurrConvOperation(AbstractConversionPartner):
    def init(self):
        super(CurrConvOperation, self).init()

    def reconciliation(self):
        super(CurrConvOperation, self).reconciliation()

    def ping(self):
        super(CurrConvOperation, self).ping()

    @shared_task(bind=True)
    def get_rates(self, api_config=None, _from=None, to_=None):
        ConversionAPI_key = 'b7ee3b79d0c745d1677d'
        try:
            url = str(api_config['url'])
            partner = apps.get_model('bemoSenderr.Partner').objects.filter(type=PartnerType.conversion).first()
            if partner:
                credentials = partner.api_user.credentials
                url = url.replace('from', _from).replace('to',to_).replace('api_key', credentials['api_key'])
                res = requests.get(url)
                #res = requests.get(f"https://free.currconv.com/api/v7/convert?q={_from}_{to_}&compact=ultra&apiKey={api_config['api_key']}")
                res = res.json()
                print('this is the response from currconv ', res)
                origin_currency = str(_from).upper()
                destination_currency = str(to_).upper()
                print('origin : ', origin_currency, 'destination : ', destination_currency)
                return res[f'{origin_currency}_{destination_currency}']
        except Exception as e:
            print(f'Cannot get rates due to {e.args}')
        debug(self)
