"""
Main file for serializers declaration used by the API

"""
# from django.contrib.auth.models import User
from rest_framework import serializers
from bemosenderrr.models import User
from bemosenderrr.models.base import GlobalTransactionStatus
from bemosenderrr.models.global_transaction import GlobalTransaction
from bemosenderrr.models.partner.bank_verification import UserBankVerificationRequest
from bemosenderrr.models.partner.kyc_verification import KycVerificationRequest
from bemosenderrr.models.partner.partner import TransactionMethodAvailability, PartnerExchangeRate, ExchangeRateTier, UserTier


class UserSerializer(serializers.ModelSerializer):
    """
    /users/
    """

    class Meta:
        model = User
        fields = ['username', 'phone_number', 'locale', 'uuid', 'email', 'first_name', 'last_name', 'last_login', 'created_at', 'updated_at']


class GlobalTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = GlobalTransaction
        fields = ('uuid', '_version', 'status', 'receiver_snapshot','user_snapshot', 'parameters', 'exchange_rate_tier_snapshot','funding_method', 'collect_method',)


class KycVerificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = KycVerificationRequest
        exclude = ("user",)


class UserVerificationByBankSerializer(serializers.ModelSerializer):

    class Meta:
        model = UserBankVerificationRequest
        exclude = ("user",)


class PartnerExchangeRateSerializer(serializers.ModelSerializer):

    class Meta:
        model = PartnerExchangeRate
        fields = '__all__'


class ExchangeRateTierSerializer(serializers.ModelSerializer):

    class Meta:
        model = ExchangeRateTier
        fields = '__all__'


class PartnerMethodsAvailabilitySerializer(serializers.ModelSerializer):

    class Meta:
        model = TransactionMethodAvailability
        fields = '__all__'


class UserTierSerializer(serializers.ModelSerializer):

    class Meta:
        model = UserTier
        fields = '__all__'


class GetChargesByAmountForWebsiteSerializer(serializers.Serializer):
    amount = serializers.FloatField(help_text="The amount ", required=True, )
    originCountryCode = serializers.CharField(label="Origin Country ISO Code", help_text="The origin country iso code", required=False)
    destinationCountryCode = serializers.CharField(label="Destination Country ISO Code", help_text="The destination country iso code", required=False, )
    options = serializers.JSONField(help_text="""The currency options, default : {"is_destination_amount":false}""", required=False, initial={"is_destination_amount":False})

    class Meta:
        fields = "__all__"


class GetChargesByAmountAPISerializer(serializers.Serializer):
    amount = serializers.CharField(help_text="The amount ", required=True, )
    origin_country = serializers.CharField(label="Origin Country ISO Code", help_text="The origin country iso code", required=True)
    destination_country = serializers.CharField(label="Destination Country ISO Code", help_text="The destination country iso code", required=True, )

    class Meta:
        fields = "__all__"


class AuthorizeDepositsSerializer(serializers.Serializer):
    start_date = serializers.CharField(help_text="Start Date 'YYYY-MM-DD'", required=False, )
    end_date = serializers.CharField(help_text="Start Date 'YYYY-MM-DD", required=False)

    class Meta:
        fields = "__all__"


class CheckDepositsSerializer(serializers.Serializer):
    start_date = serializers.CharField(help_text="Start Date 'YYYY-MM-DD'", required=False, )
    end_date = serializers.CharField(help_text="Start Date 'YYYY-MM-DD", required=False)

    class Meta:
        fields = "__all__"


class CheckRefundsSerializer(serializers.Serializer):
    start_date = serializers.CharField(help_text="Start Date 'YYYY-MM-DD'", required=False, )
    end_date = serializers.CharField(help_text="Start Date 'YYYY-MM-DD", required=False)

    class Meta:
        fields = "__all__"


class GetDestinationCountriesSerializer(serializers.Serializer):
    origin_country = serializers.CharField(label="Origin Country ISO Code", help_text="The origin country iso code", required=True)

    class Meta:
        fields = "__all__"


class GetUserMaxTransactionValueSerializer(serializers.Serializer):
    kyc_level = serializers.CharField(label="KYC Level", help_text="The KYC Level of the User", required=True)
    origin_currency = serializers.CharField(label="Origin Currency ISO Code", help_text="The origin currency iso code", required=True)

    class Meta:
        fields = "__all__"


class RegisterUserDeviceSerializer(serializers.Serializer):
    device_type = serializers.CharField(help_text="android or ios", required=True)
    device_token = serializers.CharField(help_text="The device token (FCM token)", required=True)
    app_version = serializers.CharField( help_text="The App version", required=True)
    time_zone = serializers.CharField(help_text="The timezone of the user", required=True)
    device_data = serializers.JSONField(help_text="The device data (JSON)", required=False)
    gcm_senderrid = serializers.CharField(help_text="The GCM senderrID", required=False)
    app_identifier = serializers.CharField(help_text="The App identifier", required=False)
    installation_id = serializers.CharField(help_text="The installation ID", required=False)

    class Meta:
        fields = "__all__"


class CancelGlobalTransactionSerializer(serializers.Serializer):
    uuid = serializers.CharField(label="GlobalTransaction UUID", help_text="The PK of the GlobalTransaction", required=True)
    status = serializers.ChoiceField(label="GlobalTransactionStatus", help_text="The current GlobalTransaction Status", required=True, choices=GlobalTransactionStatus.choices)

    class Meta:
        fields = "__all__"


class bemosenderrrAPISerializer(serializers.Serializer):
    request_schema = {
    "request": {
        "service": {
            "name": "GetPayment",
            "version": "1.2",
            "data": {
            }
        }
    }
}
    request = serializers.JSONField(label="Request data", help_text="The request data JSON", required=True, initial=request_schema )

    class Meta:
        fields = "__all__"


class SendEmailConfirmationSerializer(serializers.Serializer):
    user_id = serializers.CharField(label="Username", help_text="The user USERNAME (a UUID)", required=True)
    email = serializers.CharField(label="Email", help_text="The user email", required=True)

    class Meta:
        fields = "__all__"


class DisableUserSerializer(serializers.Serializer):
    user_id = serializers.CharField(label="Username (a UUID)", help_text="The Django User USERNAME (a UUID)", required=True)
    
    class Meta:
        fields = "__all__"


class EnableUserSerializer(serializers.Serializer):
    user_id = serializers.CharField(label="Username (a UUID)", help_text="The Django User USERNAME (a UUID)", required=True)
    
    class Meta:
        fields = "__all__"

class GetMobileNetworksAvailibilitiesSerializer(serializers.Serializer):
    destination_country = serializers.CharField(label="Destination country iso code", help_text="Destination country iso code", required=True)
    
    class Meta:
        fields = "__all__"


class FlinksIframURLSerializer(serializers.Serializer):
    iframe_url = serializers.CharField()

