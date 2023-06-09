from bemoSenderr.models.base import VerificationStatus
from bemoSenderr.models.user import AdminAlerts

"""
This class is mainly used for generating sms and push notifications 
Default language value for receivers is FR
Language used for sender push notifications depends on the user locale (user.locale)
"""

class NotificationsHandler():

    def get_staff_users_emails(self):
        staff_users = AdminAlerts.objects.filter(can_receive_admin_alerts=True)
        emails = []
        for staff_user in staff_users:
            emails.append(staff_user.user.email)
        return emails
    
    def get_staff_users_phone_numbers(self):
        staff_users = AdminAlerts.objects.filter(can_get_receiver_sms=True)
        phone_numbers = []
        if staff_users:
            for staff_user in staff_users:
                phone_numbers.append(staff_user.user.phone_number)
        return phone_numbers
    
    def get_tx_collect_ready_sender_push(self, lang="FR", vars=[]):
        if len(vars) != 0:
            if lang == "FR":
                return f"{vars[0]} / {vars[1]} ont été envoyé à {vars[2]} ({vars[3]})"
            elif lang == "EN":
                return f"{vars[0]} / {vars[1]} have been sent to {vars[2]} ({vars[3]})"

    def get_tx_collect_cash_ready_receiver_sms(self, lang="FR", vars=[]):
        if len(vars) != 0:
            if lang == "FR":
                """
                vars[2] contains partner names and their codes formatted.
                """
                return f"{str(vars[0]).upper()} vous a envoyé {vars[1]}. Code: {vars[2]}\n- Service client bemoSenderr {vars[3]} {vars[4]}"
            elif lang == "EN":
                return "" #TODO handle english text when it's supported by a destination country
    
    def get_tx_collect_bank_ready_receiver_sms(self, lang="FR", vars=[]):
        if len(vars) != 0:
            if lang == "FR":
                app_name = "bemoSenderr" # Can get changed at some point!
                return f"{app_name} - {vars[0]} vous a transmis {vars[1]} sur votre compte bancaire.\nCompte Bancaire: {vars[2]}\nSWIFT: {vars[3]}\nMerci d'utiliser les services {app_name} pour vos transferts d'argent."
            elif lang == "EN":
                return f"" #TODO handle english text when it's supported by a destination country

    def get_tx_collected_sender_push(self, lang="FR", vars=[]):
        if len(vars) != 0:
            if lang == "FR":
                return f"{vars[0]}, {vars[1]} a reçu votre transfert de {vars[2]} / {vars[3]}"
            elif lang == "EN":
                return f"{vars[0]}, {vars[1]} has received your transfer of {vars[2]} /{vars[3]}"

    def get_tx_funding_required_sender_push(self, lang="FR", vars=[]):
        if len(vars) != 0:
            if lang == "FR":
                if vars[3] == "0":
                    return f"Un transfert à {vars[0]} ({vars[1]}) nécessite un paiement de {vars[2]} avant d'être envoyé: {vars[4]}min. avant l'annulation automatique"
                elif vars[3] != "0" and vars[4] != "0":
                    return f"Un transfert à {vars[0]} ({vars[1]}) nécessite un paiement de {vars[2]} avant d'être envoyé: {vars[3]}h et {vars[4]}min. avant l'annulation automatique"
                else:
                    return f"Un transfert à {vars[0]} ({vars[1]}) nécessite un paiement de {vars[2]} avant d'être envoyé: {vars[3]}h. avant l'annulation automatique"
            elif lang == "EN":
                if vars[3] == "0":
                    return f"A transfer to {vars[0]} ({vars[1]}) requires a payment of {vars[2]} before being sent: {vars[4]}min. before automatic cancellation"
                if vars[3] != "0" and vars[4] != "0":
                    return f"A transfer to {vars[0]} ({vars[1]}) requires a payment of {vars[2]} before being sent: {vars[3]}h and {vars[4]}min. before automatic cancellation"
                else:
                    return f"A transfer to {vars[0]} ({vars[1]}) requires a payment of {vars[2]} before being sent: {vars[3]}h. before automatic cancellation"

    def get_tx_funding_incactivity_sender_push(self, lang="FR", vars=[]):
        if len(vars) != 0:
            if lang == "FR":
                return f"Un transfert de {vars[0]} / {vars[1]} pour {vars[2]} ({vars[3]}) à été annulé pour manque de fonds"
            elif lang == "EN":
                return f"A {vars[0]} / {vars[1]} transfer to {vars[2]} ({vars[3]}) was canceled due to missing funds"

    def get_tx_delayed_sender_push(self, lang="FR", vars=[]):
        if len(vars) != 0:
            if lang == "FR":
                return f"Une erreur est survenue durant le retrait des fonds.\n Un délai de 15 minutes est à prévoir avant que les fonds soit accessible stans une succursale {vars[0]}."
            elif lang == "EN":
                return f"An error occurred during funds withdrawal.\n A 15 minutes delay should be expected before the funds are accessible in a {vars[0]} location."

    def get_tx_delayed_receiver_sms(self, lang="FR", vars=[]):
        if len(vars) != 0:
            if lang == "FR":
                return f"Transaction retardée.\n Veuillez retourner chez {vars[0]} d'ici 15 minutes \n Service client {vars[1]}"
            elif lang == "EN":
                return f"Transaction delayed. \n Return to a {vars[0]} location in 5 to 15 minutes to receive your funds \n Customer Service {vars[1]}"

    def get_bank_verif_complete_push(self, status=None, lang="FR", vars=[]):
        if len(vars) != 0:
            if status == VerificationStatus.verified:
                if lang == "FR":
                    return f"{vars[0]}, votre compte a été vérifié avec succès"
                elif lang == "EN":
                    return f"{vars[0]}, your account was successfully verified"
            else:
                if lang == "FR":
                    return f"{vars[0]}, une erreur s'est produite durant la vérification de votre compte. Veuillez contacter le service client."
                elif lang == "EN":
                    return f"{vars[0]}, an error occurred during your account verification. Please contact customer support."