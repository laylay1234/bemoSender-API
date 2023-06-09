from django.conf import settings
from loguru import logger
from random import random
from django.apps import apps
from bemosenderrr.models.partner.partner import  PartnerApiCallType
from redbeat import RedBeatSchedulerEntry as Entry
from bemosenderrr.celery import app
from bemosenderrr.models.task import PeriodicTasksEntry


def start_collect_periodic_task(collect_operation=None, global_transaction=None):
    if collect_operation.partner.api_call_type == PartnerApiCallType.outbound:
        # Dynamic periodic task to check collect status every 10 sec (redbeat)
        logger.info(
            "Starting Collect Transactions periodic tasks " + str(collect_operation))
        api_config = collect_operation.partner.api_config
        credentials = collect_operation.partner.api_user.credentials
        api_config['credentials'] = credentials
        amount = global_transaction.parameters['amount_destination']
        transaction_code = collect_operation.collect_code
        logger.info(f"instance {collect_operation.status}")
        while not transaction_code:
            transaction_code = collect_operation.collect_code
        dh_tx_code = collect_operation.partner_response.get(
            'dirham_transaction_code', False) if collect_operation.partner_response.get('dirham_transaction_code', False) else ""
        dh_pay_code = collect_operation.partner_response.get(
            'dirham_payment_code', False) if collect_operation.partner_response.get('dirham_payment_code', False) else ""
        dam_ord_numb = collect_operation.partner_response.get(
            'damane_order_number', False) if collect_operation.partner_response.get('damane_order_number', False) else ""
        atps_transaction_code = collect_operation.partner_response.get(
            'atps_transaction_code', False) if collect_operation.partner_response.get('atps_transaction_code', False) else ""
        params = {
            "dirham_transaction_code": dh_tx_code,
            "dirham_payment_code": dh_pay_code,
            "damane_order_number": dam_ord_numb,
            "damane_amount_mad": amount,
            "atps_transaction_code": atps_transaction_code,
            "api_config": api_config,
            "collect_uuid": str(collect_operation.uuid),
            "collect_code": transaction_code,
            "gtx_uuid": str(global_transaction.uuid)
        }
        schedule = 600
        env = None
        if settings.CONFIG and settings.CONFIG.get('env', None) in ['Dev-V3', None]:
            env = "Dev-V3"
        else:
            env = "Prod-V3"
        if env == "Prod-V3":
            schedule = 900
        logger.info(f"CHECKCOLLECTSTATUS ENVIRONMENT {env}")
        try:
            
            e = Entry.from_key(key=f"redbeat:checking {str(collect_operation.uuid)} collect of {global_transaction.user} {global_transaction.uuid}", app=app)
            periodic_task, created = PeriodicTasksEntry.objects.get_or_create(key=e.key, task="bemosenderrr.models.partner.transactions.check_collect_status",
                                                                            name=e.name, args=[params]
                                                                            )
            logger.info(f"Periodic task is new {e.key}")
        except Exception as e:
            e = Entry(schedule=schedule, name=f"checking {str(collect_operation.uuid)} collect of {global_transaction.user} {global_transaction.uuid}", app=app,
                    task="bemosenderrr.models.partner.transactions.check_collect_status", args=[params])
            e.save()
            logger.info(
                "Collect Transaction periodic task args " + str(e.args))
            # Periodic task object to manage redbeat periodic tasks(entries) dynamically)
            periodic_task, created = PeriodicTasksEntry.objects.get_or_create(key=e.key, task="bemosenderrr.models.partner.transactions.check_collect_status",
                                                                            name=e.name, schedule=schedule, args=[params]
                                                                            )
            periodic_task.save()


def getTransactionId(idLength=None, stringLength=None, prefix=None):
    try:
        digits = "99999999999"  # For Damane & CashPlus - length: 11
        if (idLength):
            numberLength = idLength
            if (prefix):
                numberLength = numberLength - len(prefix)
            digits = "9"
            while (numberLength > len(digits)):
                digits += "9"
        print('TEST DESIRED LENGTH', idLength)
        print('TEST DIGITS LENGTH', len(digits), digits)
        digits = int(digits)
        print(random())
        print(digits)
        number = int(random() * digits)

        testId = str(number) + ''
        if (prefix):
            testId = prefix + testId
        print('TEST GENERATED ID')
        collect_transaction_model = apps.get_model(
            'bemosenderrr', 'CollectTransaction')
        collect_code_query = collect_transaction_model.objects.filter(
            collect_code=testId)
        if len(collect_code_query) > 0:
            print('ID EXISTS...call again with', idLength)
            return getTransactionId(idLength, stringLength, prefix)
        else:
            print('ID IS NEW...return number')
            stringLength = stringLength or idLength
            print('id length ', idLength)
            print('stringlength ', stringLength)
            s = stringLength * -1
            print(s)
            print(testId)
            number = str(f"00000000000{testId}")[s:]
            print(number)
            print(len(number))
            return testId
    except Exception as e:
        print(e.args)


def getPaymentCode(txCode):

    root = cleanField("1406", 4)
    ref = cleanField(txCode, 9)
    print(ref)
    paycode = root + '' + ref

    cdigit = CalculeCheckDigit(paycode)

    paycode += '' + str(cdigit)

    return paycode


def cleanField(string, i):
    return str(string.replace(r"/D/g", '') + '0000000000')[0:i]
    # return (str.replace(/\D/g,'') + '0000000000').substring(0, i);


def CalculeCheckDigit(code):
    x = 0
    d = 0
    for i in range(3, 10):
        x = int(code[i]) * (2 - ((i+1) % 2))
        print('current x ', x)
        if x > 9:
            x -= 9
    d = 10 - (d % 10)
    if d == 10:
        d = 0
    return d