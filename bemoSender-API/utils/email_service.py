import base64
import datetime
import email
import json
import re
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from django.apps import apps
from loguru import logger
from google.oauth2 import service_account
import six
from google.auth import crypt
from django.conf import settings
from bemoSenderr.models.partner.partner import AppSettings

"""
This module is for handling Gmail API and filtering interac emails.
"""

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
def exec(regex, s):
    if re.compile(regex).match(s):
        return True
    else:
        return False

depEmailRegex = r"^(.*) <(.*)>$"
#For autoDepRegex.amountEN: yes there is an extra space in the text....
# it comes from Interac so monitor this in case it changes :/
autoDepRegex = {
    "subjectFR": r"Virement INTERAC : Un virement de fonds de (.*) a été automatiquement déposé\.$",#TODO this is CORRECT
    "subjectEN": r"INTERAC e-Transfer: A money transfer from (.*) has been automatically deposited",#TODO this is CORRECT
    "msgEN": r"Reference Number[ ]*:[ ]*(.*)",
    "msgFR": r"Numéro de référence[ ]*:[ ]*(.*)",
    "amountEN": r"has sent you a money transfer for the amount of [ ]*\$(.*)[ ]*\(CAD\)[ ]*and the money has been automatically deposited into your bank account",
    "amountFR": r"vous a envoyé[ ]*(.*)[ ]*\$[ ]*\(CAD\)[ ]*et les fonds ont été automatiquement déposés stans votre compte bancaire",
}
manualDepRegex = {
    "subjectEN": r"INTERAC e-Transfer[ ]?:[ ]*(.*)[ ]*sent you money\.$", #TODO this is CORRECT
    "subjectFR": r"Virement INTERAC[ ]?:[ ]*(.*)[ ]*vous a envoyé des fonds\.$",#TODO this is CORRECT
    "msgEN": r"https:\/\/etransfer.interac.ca\/(.*)\/(.*)",
    "msgFR": r"https:\/\/etransfer.interac.ca\/fr\/(.*)\/(.*)",
    "amountEN": r"sent you a money transfer for the amount of[ ]*\$(.*)[ ]*\(CAD\)[ ]*\.",
    "amountFR": r"vous a envoyé un virement de[ ]*(.*)[ ]*\$[ ]*\(CAD\)[ ]*\.",
}
class EmailService:

    def from_authorized_user_file(self, data, scopes=None):
        return Credentials.from_authorized_user_info(data, scopes)

    def _from_signer_and_info(self, signer, info, **kwargs):
        return service_account.Credentials(
            signer,
            service_account_email=info["client_email"],
            token_uri=info["token_uri"],
            project_id=info.get("project_id"),
            **kwargs
        )

    def from_dict(self, data, require=None):
        keys_needed = set(require if require is not None else [])

        missing = keys_needed.difference(six.iterkeys(data))

        if missing:
            raise ValueError(
                "Service account info was not in the expected format, missing "
                "fields {}.".format(", ".join(missing))
            )

        # Create a signer.
        signer = crypt.RSASigner.from_service_account_info(data)

        return signer

    def from_filename(self, data, require=None):
        return data, self.from_dict(data, require=require)

    def from_service_account_file(self, filename, **kwargs):
        info, signer = self.from_filename(
            filename, require=["client_email", "token_uri"]
        )
        return service_account.Credentials._from_signer_and_info(signer, info, **kwargs)
    def get_service(self):
        service = None
        try:
            creds = None
            # The file token.json stores the user's access and refresh tokens, and is
            # created automatically when the authorization flow completes for the first
            # time.
            gmail_partner = apps.get_model('bemoSenderr', "Partner").objects.get(name="Gmail")
            credentials = gmail_partner.api_user.credentials
            appsettings = AppSettings.objects.first()
            deposit_email = appsettings.config.get("interacDeposit", None).get("mailbox", None)
            creds = self.from_service_account_file(
                filename=credentials,
                scopes=SCOPES,
                subject=deposit_email
                )
            try:
                # Call the Gmail API
                service = build('gmail', 'v1', credentials=creds)
                results = service.users().labels().list(userId='me').execute()
                labels = results.get('labels', [])

                if not labels:
                    print('No labels found.')
                    return

            except HttpError as error:
                # TODO(developer) - Handle errors from gmail API.
                print(f'An error occurred: {error}')
            service = build('gmail', 'v1', credentials=creds)
            print('Service successfully acquired')
            return service
        except Exception as e:
            logger.info(str(e))
            return service
    def get_service_2(self):
        service = None
        try:
            """Shows basic usage of the Gmail API.
            Lists the user's Gmail labels.
            """
            creds = None
            # The file token.json stores the user's access and refresh tokens, and is
            # created automatically when the authorization flow completes for the first
            # time.
            gmail_partner = apps.get_model('bemoSenderr', "Partner").objects.get(name="Gmail")
            credentials = gmail_partner.api_user.credentials
            token = {
                "token": credentials['token'],
                "refresh_token": credentials['refresh_token'],
                "token_uri": credentials['token_uri'],
                "client_id": credentials['client_id'],
                "client_secret": credentials['client_secret'],
                "scopes": credentials['scopes'],
                "expiry": credentials['expiry']
            }
            creds = self.from_authorized_user_file(token, SCOPES)
            # If there are no (valid) credentials available, let the user log in.
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                    logger.info("GMAIL CREDENTIALS EXPIRED .. REFRESHING")
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        'credentials.json', SCOPES)
                    creds = flow.run_local_server(port=8001,host='127.0.0.1')
                    logger.info("GMAIL CREDENTIALS NOT FOUND ! ACQUIRE NEW ONES with the local server !")
                # Save the credentials for the next run
                #with open('token.json', 'w') as token:
                #    token.write(creds.to_json())

            try:
                # Call the Gmail API
                service = build('gmail', 'v1', credentials=creds)
                results = service.users().labels().list(userId='me').execute()
                labels = results.get('labels', [])

                if not labels:
                    print('No labels found.')
                    return
                print('Labels:')
                for label in labels:
                    print(label['name'])

            except HttpError as error:
                # TODO(developer) - Handle errors from gmail API.
                print(f'An error occurred: {error}')
            service = build('gmail', 'v1', credentials=creds)
            print('Service successfully acquired')
            return service
        except Exception as e:
            logger.info(str(e))
            return service

    def data_encoder(self, text):
        if text and len(text)>0:
            message = base64.urlsafe_b64decode(text.encode('UTF8'))
            message = str(message, 'utf-8')
            message = email.message_from_string(message)
            return message
        else:
            return None
    

    def read_message(self, content)->str:
        import copy
        if content.get('payload').get('parts', None):
            parts = content.get('payload').get('parts', None)
            sub_part = copy.deepcopy(parts[0])
            while sub_part.get("mimeType", None) != "text/plain":
                try:
                    sub_part = copy.deepcopy(sub_part.get('parts', None)[0])
                except Exception as e:
                    break
            return self.data_encoder(sub_part.get('body', None).get('data', None)).as_string()
        else:
            return content.get("snippet")
    """
    def read_message_2(self, content)->str:
        message = None
        if "data" in content['payload']['body']:
            message = content['payload']['body']['data']
            message = self.data_encoder(message)
        elif "data" in content['payload']['parts'][0]['body']:
            message = content['payload']['parts'][0]['body']['data']
            message = self.data_encoder(message)
        else:

            message = content['payload']['parts'][0]['parts'][0]['parts'][0]['body']['data']
            message = self.data_encoder(message)
        return message.as_string()
    """    
    def search_msg(self, value, msgSrc):
        for p in msgSrc:
            if p['name'] == value:
                return p['value']

    def filterEmailParams(self, msgSrc):
        data = {}
        reply_to = self.search_msg("Reply-To", msgSrc.get("payload").get("headers"))
        subject = self.search_msg("Subject", msgSrc.get("payload").get("headers"))
        email_internal_date = msgSrc['internalDate']
        email_body = self.read_message(msgSrc)
        #logger.info(email_body)
        data['reply_to'] = reply_to
        data['subject'] = subject
        data['email_internal_date'] = email_internal_date
        data['email_body'] = email_body
        return data

    def filterDepositEmailData(self, msgSrc, typeQuery=None):
        report = ''
        try:
            type = lang = data = None
            filtered_email_data = self.filterEmailParams(msgSrc)
            timestamp = filtered_email_data.get('email_internal_date', None)
            internal_time = datetime.datetime.utcfromtimestamp(float(filtered_email_data.get('email_internal_date', None))/ 1000)
            # PREPARE VARIABLES
            activeRegex = clientMatch = refCodeMatch = amountMatch = None
            report = ''
            data = None
            emailDate = datetime.datetime.strftime(internal_time, "%Y-%m-%d %H:%M:%S.%f") #
            emailMatch = re.search(depEmailRegex,filtered_email_data['reply_to']) 
            clientMatchEN_auto = re.search(autoDepRegex["subjectEN"],filtered_email_data['subject'], re.IGNORECASE)
            clientMatchFR_auto = re.search(autoDepRegex["subjectFR"], filtered_email_data['subject'], re.IGNORECASE)
            clientMatchEN_manual = re.search(manualDepRegex["subjectEN"],filtered_email_data['subject'], re.IGNORECASE)
            clientMatchFR_manual = re.search(manualDepRegex["subjectFR"],filtered_email_data['subject'], re.IGNORECASE)
            
            report += f"EMAIL DATE: {emailDate}\n"
            report += f"TEST EMAIL MATCH: {filtered_email_data['reply_to']}\n"
            report += f"  emailMatch REGEX: {depEmailRegex}\n"
            report += f"  emailMatch:\n{emailMatch[0]}\n"
            report += f"\nTEST CLIENT MATCH: {filtered_email_data['subject']}\n"
            report += f"  clientMatchEN_auto REGEX: {autoDepRegex['subjectEN']} \n"
            report += f"  clientMatchEN_auto: {clientMatchEN_auto}\n"
            report += f"  clientMatchEN_auto REGEX: {autoDepRegex['subjectFR']} \n"
            report += f"  clientMatchFR_auto: {clientMatchFR_auto}\n"
            report += f"  clientMatchEN_manual REGEX: {manualDepRegex['subjectEN']}\n"
            report += f"  clientMatchEN_manual: {clientMatchEN_manual}\n"
            report += f"  clientMatchFR_manual REGEX: {manualDepRegex['subjectFR']}\n"
            report += f"  clientMatchFR_manual: {clientMatchFR_manual}\n"
            if (clientMatchEN_auto or clientMatchFR_auto):
                activeRegex = autoDepRegex
                type = 'auto'
                lang = 'EN'
                clientMatch = clientMatchEN_auto
                if (clientMatchFR_auto):
                    lang = 'FR'
                    clientMatch = clientMatchFR_auto
                #logger.info(f'EMAIL BODY {filtered_email_data["email_body"]}')
            elif (clientMatchEN_manual or clientMatchFR_manual):
                activeRegex = manualDepRegex
                type = 'manual'
                lang = 'EN'
                clientMatch = clientMatchEN_manual
                if (clientMatchFR_manual):
                    lang = 'FR'
                    clientMatch = clientMatchFR_manual

            report += f"\nTEST EMAIL DATA\n  LANG: ${lang}\n  TYPE: ${type}\n  QUERY ONLY TYPE ${typeQuery}\n"
            
            # SKIP EMAIL if no type OR if type doesn't match queried type
            if (not type):
                report += "\nSKIPPED...NO TYPE FOUND"
                return [[filtered_email_data["subject"], emailDate, filtered_email_data["reply_to"]], report]
            if (typeQuery):
                if (typeQuery.lower() != type.lower()):
                    report += "\nSKIPPED...QUERIED TYPE DOES NOT MATCH EMAIL TYPE"
                    return [[filtered_email_data["subject"], emailDate, filtered_email_data["reply_to"]], report]
            amountMatch = re.search(activeRegex[f"amount{lang}"], filtered_email_data["email_body"], re.IGNORECASE)
            refCodeMatch = re.search(activeRegex[f"msg{lang}"], str(filtered_email_data['email_body']), re.IGNORECASE)
            if clientMatchEN_auto and not amountMatch:
                en_regex = r"has sent you a money transfer for the amount of [ ]*(.*)[ ]*\$[ ]*\(CAD\)[ ]*and the money has been automatically deposited into your bank account"
                amountMatch = re.search(en_regex, filtered_email_data["email_body"], re.IGNORECASE)
            if (clientMatch and refCodeMatch and amountMatch):
                if clientMatchEN_auto:
                    amount = str(amountMatch[1]).replace(',', '.').replace(r"[.,]{1}([0-9]{2})[ ]*$", '.$1').replace(' ', '')
                else:
                    amount = str(amountMatch[1]).replace(r"[.,]{1}([0-9]{2})[ ]*$", '.$1').replace(' ', '')
                if lang == "FR":
                    if "." in amount and "," in amount:
                        amount = str(amount).replace(",", "")
                    elif "," in amount and "." not in amount:
                        amount = str(amount).replace(",", ".")
                if lang == "EN":
                    amount = str(amount).replace(",", "")
                data = dict({
                    "client" : emailMatch[1] if clientMatch[0] else None,
                    "clientEmail" : emailMatch[2] if emailMatch[2] else None,
                    "refCode" : refCodeMatch[1] if refCodeMatch[1] else None,
                    "amount": amount ,
                    "utctimestamp": emailDate ,
                    "localtimestamp": emailDate,
                    "depositType": type,
                    "lang":lang,
                    "email": dict({
                        "subject": filtered_email_data['subject'],
                        "replyTo": filtered_email_data['reply_to'],
                        "body": str(filtered_email_data['email_body']).replace('\n', " ")
                    })
                })
                report = f"GOT REQUIRED DETAILS\n{json.dumps({ 'emailDate': data['utctimestamp'], 'client': data['client'], 'clientEmail': data['clientEmail'], 'refCode': data['refCode'], 'amount': data['amount']})}\n"
                return [data, report]
            else:
                return [[filtered_email_data["subject"], emailDate, filtered_email_data["reply_to"]], report]
        except Exception as e:
            print(e)
            return ['', report]
