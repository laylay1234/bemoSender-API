import copy
import json
import os
import urllib.parse
from django.contrib.auth.models import Group
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.translation import ugettext_lazy as _
from gql import gql
from loguru import logger
from pickles.api.views import PicklesAPIView
from pickles.models import Pickle
from rest_framework import viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework_guardian.filters import ObjectPermissionsFilter
from bemosenderrr.models.base import CollectTransactionStatus, GlobalTransactionStatus, PartnerStatus, PartnerType
from bemosenderrr.models.global_transaction import GlobalTransaction
from bemosenderrr.models.partner.bank_verification import UserBankVerificationRequest
from bemosenderrr.models.partner.kyc_verification import KycVerificationRequest
from bemosenderrr.models.partner.partner import Country, MobileNetworkAvailability, Partner, ExchangeRateTier, PartnerExchangeRate, UserTier
from bemosenderrr.models.partner.services.apaylo_service import ApayloService
from bemosenderrr.models.partner.services.dirham_service import DirhamService
from bemosenderrr.models.partner.transactions import TxLimitCumul
from bemosenderrr.models.task import PeriodicTasksEntry
from bemosenderrr.utils.mutation_queries import UPDATE_USER_MUTATION
from bemosenderrr.utils.pinpoint import PinpointWrapper
from bemosenderrr.bemosenderrr_api.bemosenderrr_api import bemosenderrr_api
from bemosenderrr.models.user import User, UserToken
from rest_framework.generics import GenericAPIView, ListAPIView, RetrieveAPIView
from rest_framework.mixins import RetrieveModelMixin, UpdateModelMixin, CreateModelMixin
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from bemosenderrr.operations import TxLimitCumulOperations
from bemosenderrr.serializers import UserSerializer
from bemosenderrr.permissions import IsAPIUser, IsNotAPIUser, APIUserPermissionMixins
from bemosenderrr.serializers.serializers import *
from bemosenderrr.tasks import check_refunds, update_pending_sign_up_flinks, update_rates, check_deposits, authorize_deposits
from rest_framework import status
import pprint
from bemosenderrr.utils.appsync import make_client
from bemosenderrr.services import sync_email_verification
from bemosenderrr.utils.email_service import SCOPES, EmailService
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import authentication_classes, permission_classes
import boto3
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from rest_framework.decorators import action


@api_view(['GET'])
def index(request, format=None):
    index.cls.__doc__ = _("""
    Welcome to [bemosenderrr][ref2].
    
    This page returns a list of all API endpoints in the system.

    For more details on how to use this platform [see here][ref].

    [ref2]: http://support.bemosenderrr.app
    [ref]: https://bemosenderrr.dev/v1/redoc/
    """)
    # log(request.version)
    if request.user.is_staff:
        if request.LANGUAGE_CODE == 'fr':
            response = Response({
                'me': reverse('user-detail', request=request, format=format),
                'Send Money API': reverse('v1:send-money-list', request=request, format=format),
                "User Verification By Bank":reverse('v1:user-bank-verify-list', request=request, format=format),
                "KYC Verification Request":reverse('v1:kyc-verify-list', request=request, format=format),
                'Check Deposits': reverse('check-deposits', request=request, format=format),
                'Authorize Deposits': reverse('authorize-deposits', request=request, format=format),
                'Check Refunds': reverse('check-refunds', request=request, format=format),
                'Update Rates': reverse('update-rates', request=request, format=format),
                'Get destination countries': reverse('get-destination-countries', request=request, format=format),
                'Get charges by amount (bemosenderrr APP)': reverse('get-charges-by-amount', request=request, format=format),
                'bemosenderrr API': reverse('bemosenderrr-api', request=request, format=format),
                "Cancel a Global Transaction": reverse('cancel-global-transaction', request=request, format=format),
                "Get Charges by amount (bemosenderrr website)":reverse('getChargesByAmount', request=request, format=format),
                "Get Origin Countries":reverse('get-origin-countries', request=request, format=format),
                "Get User Max Transaction Value":reverse('get-user-max-tx-value', request=request, format=format),
                "Register User Device and Token":reverse('register-device', request=request, format=format),
                "Send Confirmation Email":reverse('send-email', request=request, format=format),
                "Block User":reverse('block-user', request=request, format=format),
                "Enable User":reverse('enable-user', request=request, format=format),
                "Mobile Networks Availability":reverse('get-mobile-networks', request=request, format=format),
                "Init Config API": reverse('init-api', request=request, format=format),
                "Flinks Iframe URL API": reverse('flinks-iframe-api', request=request, format=format),
                "Test Pending Flinks Async Requests Task": reverse('test-pending-flinks', request=request, format=format)

                #'customfields': reverse('customfield-list', request=request, format=format),
            })
        else:
            response = Response({
                'me': reverse('user-detail', request=request, format=format),
                'Send Money API': reverse('v1:send-money-list', request=request, format=format),
                "User Verification By Bank":reverse('v1:user-bank-verify-list', request=request, format=format),
                "KYC Verification Request":reverse('v1:kyc-verify-list', request=request, format=format),
                'Check Deposits': reverse('check-deposits', request=request, format=format),
                'Authorize Deposits': reverse('authorize-deposits', request=request, format=format),
                'Check Refunds': reverse('check-refunds', request=request, format=format),
                'Update Rates': reverse('update-rates', request=request, format=format),
                'Get destination countries': reverse('get-destination-countries', request=request, format=format),
                'Get charges by amount (bemosenderrr APP)': reverse('get-charges-by-amount', request=request, format=format),
                'bemosenderrr API': reverse('bemosenderrr-api', request=request, format=format),
                "Cancel a Global Transaction": reverse('cancel-global-transaction', request=request, format=format),
                "Get Charges by amount (bemosenderrr website)":reverse('getChargesByAmount', request=request, format=format),
                "Get Origin Countries":reverse('get-origin-countries', request=request, format=format),
                "Get User Max Transaction Value":reverse('get-user-max-tx-value', request=request, format=format),
                "Register User Device and Token":reverse('register-device', request=request, format=format),
                "Send Confirmation Email":reverse('send-email', request=request, format=format),
                "Block User":reverse('block-user', request=request, format=format),
                "Enable User":reverse('enable-user', request=request, format=format),
                "Mobile Networks Availability":reverse('get-mobile-networks', request=request, format=format),
                "Init Config API": reverse('init-api', request=request, format=format),
                "Flinks Iframe URL API": reverse('flinks-iframe-api', request=request, format=format),
                "Test Pending Flinks Async Requests Task": reverse('test-pending-flinks', request=request, format=format)

                #'customfields': reverse('customfield-list', request=request, format=format),
            })
        return response
    else:
        return Response({"response": "You do not have permission to perform this action."})


class UserModelViewSet(RetrieveModelMixin, UpdateModelMixin, CreateModelMixin, GenericAPIView):
    serializer_class = UserSerializer
    permission_classes = (IsAuthenticated, IsNotAPIUser)
    filter_backends = [ObjectPermissionsFilter, DjangoFilterBackend]


class UserProfileAPI(RetrieveModelMixin, UpdateModelMixin, GenericAPIView):
    serializer_class = UserSerializer
    permission_classes = (IsAuthenticated, IsNotAPIUser)
    filter_backends = [ObjectPermissionsFilter, DjangoFilterBackend]

    def get_object(self):
        return self.request.user

    def get(self, request, *args, **kwargs):
        """
        User profile

        Get profile of current logged in user.
        """
        return self.retrieve(request, *args, **kwargs)

    def patch(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)

    def perform_update(self, serializer):
        super(UserProfileAPI, self).perform_update(serializer)
        try:
            self.request.user.groups.get(name='user')
        except Group.DoesNotExist:
            group, created = Group.objects.get_or_create(name="user")
            self.request.user.groups.add(group)


class GlobalTransactionViewSet(viewsets.ModelViewSet):

    __doc__ = _("""
    API endpoint that GlobalTransaction to be created.
    """)
    ordering = ('updated_at', 'uuid')
    ordering_fields = ('updated_at', 'uuid')
    search_fields = ['user', 'uuid']
    lookup_field = 'uuid'
    permission_classes = [IsNotAPIUser, IsAuthenticated]
    http_method_names = ['get', 'post', 'put', 'head', 'patch']
    serializer_class = GlobalTransactionSerializer
    filter_backends = [ObjectPermissionsFilter, DjangoFilterBackend]

    def get_queryset(self):
        user = self.request.user
        return GlobalTransaction.objects.filter(user=user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        cleaned_data = serializer.data
        return Response(cleaned_data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        serializer.validated_data['user'] = self.request.user
        print('global transaction uuid', self.request.data['uuid'])
        serializer.save(uuid=self.request.data['uuid'], _version=1)


    def patch(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)


class KycVerificationViewSet(viewsets.ModelViewSet):
    __doc__ = _("""
    API endpoint that KycVerificationRequest to be created.
    """)
    ordering = ('updated_at', 'uuid')
    ordering_fields = ('updated_at', 'uuid')
    search_fields = ['user', 'uuid']
    filter_backends = [ObjectPermissionsFilter, DjangoFilterBackend]
    lookup_field = 'uuid'
    serializer_class = KycVerificationSerializer
    permission_classes = [IsAuthenticated, IsNotAPIUser]

    def get_queryset(self):
        return KycVerificationRequest.objects.filter(user=self.request.user)

    def perform_create(self, serializer):

        user_snapshot = serializer.validated_data['user_snapshot']
        user = User.objects.filter(username=user_snapshot['uuid']).first()
        if not user:
            print("No user found matching this username!")
            return
        serializer.validated_data['user'] = user

        try:
            last_kyc_request = KycVerificationRequest.objects.filter(user=user).latest('created_at')
            user_snapshot_new = dict(user_snapshot)
            del user_snapshot_new['state']
            del user_snapshot_new['email']
            del user_snapshot_new['birth_date']
            print(user_snapshot_new)
            last_user_snapshot = dict(last_kyc_request.user_snapshot)
            del last_user_snapshot['state']
            del last_user_snapshot['email']
            del last_user_snapshot['birth_date']
            print(last_user_snapshot)
            if last_user_snapshot == user_snapshot_new:
                print('user data didnt change!')
                return
            query_counter = int(last_kyc_request.query_counter) + 1
            serializer.validated_data['query_counter'] = query_counter
        except Exception as e:
            print('KYC INSTANCE IS NEW QUERY_COUNTER = 1', e)
            serializer.validated_data['query_counter'] = 1
        partner = Partner.objects.filter(type=PartnerType.kyc_verification, status=PartnerStatus.active).first()
        print(partner)
        if partner:
            serializer.validated_data['partner'] = partner
        serializer.save()


class UserVerificationByBankViewSet(viewsets.ModelViewSet):
    __doc__ = _("""
    API endpoint that UserBankVerificationRequest to be created.
    """)
    ordering = ('updated_at', 'uuid')
    ordering_fields = ('updated_at', 'uuid')
    search_fields = ['user', 'uuid']
    filter_backends = [ObjectPermissionsFilter, DjangoFilterBackend]
    lookup_field = 'uuid'
    serializer_class = UserVerificationByBankSerializer
    def get_queryset(self):
        return UserBankVerificationRequest.objects.filter(user=self.request.user)

    def get_permissions(self):

        if self.action == 'create':
            self.permission_classes = (AllowAny, )
        else:
            self.permission_classes = (IsNotAPIUser, IsAuthenticated)
        return [permission() for permission in self.permission_classes]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_data = self.perform_create(serializer)
        response = copy.deepcopy(serializer.data)
        response.pop('partner_response', None)
        response.pop('partner', None)
        response.pop('partner_parameters', None)
        response.pop('status', None)
        response.pop('_version', None)
        logger.info(user_data)
        if user_data and isinstance(user_data, dict):
            logger.info('SUCCESSFULY GOT THE DATA')
            response['user_data'] = user_data
            response['verified'] = "True"
        elif user_data and isinstance(user_data, str):
            logger.info('OPERATION STILL PENDING')
            response['verified'] = "Pending"
            response['request_id'] = user_data
            
        else:
            logger.info('the else ')
            response['verified'] = "False"
        headers = self.get_success_headers(serializer.data)
        return Response(response, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        user = None
        if self.request.user and isinstance(self.request.user, User):
            user = self.request.user
            serializer.validated_data['user'] = user
        partner = Partner.objects.filter(type=PartnerType.bank_verification, status=PartnerStatus.active).first()
        if partner:
            serializer.validated_data['partner'] = partner
        if partner and user:
            logger.info('FLINKS USER EXISTS')
            user = self.request.user
            self.update_bank_verification_status_pending(user=user)
            instance = serializer.save()
            api_config = instance.partner.api_config
            instance.verify.apply_async((api_config, str(instance.uuid)))
            return instance.uuid
        elif partner and not user:
            logger.info('FLINKS SIGN UP FLOW')
            instance = serializer.save()
            api_config = instance.partner.api_config
            if instance.partner.api_user:
                api_config['credentials'] = instance.partner.api_user.credentials
            user_data = instance.verify(api_config, str(instance.uuid))
            logger.info(f"the user data {user_data}")
            return user_data
        
    @action(detail=True, methods=['POST'], url_path="assign-user", url_name="assign-user", name='assign-user')
    def assign_user(self, request, uuid):
        UserBankVerificationRequest.objects.filter(uuid=uuid).update(user=request.user)
        queryset = UserBankVerificationRequest.objects.get(uuid=uuid)
        serializer = UserVerificationByBankSerializer(queryset, many=False)
        headers = self.get_success_headers(serializer.data)
        response = copy.deepcopy(serializer.data)
        response.pop('partner_response', None)
        response.pop('partner', None)
        response.pop('partner_parameters', None)
        response.pop('status', None)
        response.pop('_version', None)
        return Response(response, status=status.HTTP_200_OK, headers=headers)


    def update_bank_verification_status_pending(self, user):
        try:
            params = {
                "id": str(user.username),
                "bank_verification_status": "IN_PROGRESS"
            }
            client = make_client()
            query = UPDATE_USER_MUTATION
            response = client.execute(gql(query), variable_values=json.dumps({'input': params}))
            if response.get('updateUser', None):
                print("SYNC IN_PROGRESS FOR FLINKS", response.get('updateUser').get('bank_verification_status', None))
            else:
                print("ERROR SYNCING IN_PROGRESS bank_verification_status ", response)
        except Exception as e:
            print("ERROR SYNCING IN_PROGRESS bank_verification_status ", e)


class UserTierAPI(ListAPIView):

    permission_classes = [IsAuthenticated, IsNotAPIUser]
    serializer_class = UserTierSerializer
    queryset = UserTier.objects.all()
    filter_backends = [ObjectPermissionsFilter, DjangoFilterBackend]


def get_daily_account_statement(request):
    body_unicode = request.body.decode('utf-8')
    body = json.loads(body_unicode)
    reqBody = body
    partner = reqBody['partner_name']
    partner = Partner.objects.get(display_name=partner)
    api_config = partner.api_config
    api_config['credentials'] = partner.api_user.credentials
    response = DirhamService.get_daily_account_statement(api_config=api_config)
    if response:
        return JsonResponse({"response":response.json()})
    else:
        return JsonResponse({'response':'server error'})


def update_rates_test(request):
    update_rates()
    return JsonResponse({'response':"success"})


@api_view(http_method_names=['POST'])
def test_gmail(request):
    if not request.user.is_staff:
        return Response({"response":"Unauthorized to make this call"}, status=403)
    if request.data:
        start_date = request.data.get('start_date', None)
        end_date = request.data.get('end_date', None)
    else:
        return JsonResponse({"response": "YOU MUST PROVIDE start_date and end_date"})
    email_service = EmailService()
    service = email_service.get_service()
    mail = service.users().messages().list(userId='me', labelIds=['INBOX'], q=f'after: {start_date} before: {end_date}').execute()
    messages = mail.get('messages')
    logger.info(messages)
    #email_data = list()
    i = 0
    if messages:
        logger.info(len(messages))
        for email in messages:
            temp_report = ''
            message = service.users().messages().get(userId='me', id=email['id'], format="full").execute()
            pp = pprint

            data = email_service.filterDepositEmailData(message)
            i = i + 1
            if isinstance(data[0], dict):
                item = data[0]
                #logger.info(item)
                ref_code = item.get('refCode', None)
                client_email = item.get('clientEmail', None)
                body = item.get('email', None).get('body', None) if item.get('email') else None
                amount = item.get('amount', None)
                logger.info(f'EMAIL N° {i}')
                logger.info(f"UTC TIMESTAMP {item.get('utctimestamp')}")
                logger.info(f"REFERENCE CODE : {ref_code}")
                logger.info(f"CLIENT EMAIL : {client_email}")
                logger.info(f'THE EMAIL AMOUNT {amount}')
                logger.info(f"EMAIL BODY : {body}")
            logger.info('-------------------------------------------')

    return JsonResponse({"response":"success"})

class CheckDepositsAPI(APIView):
    serializer_class = CheckDepositsSerializer
    permission_classes = [IsNotAPIUser, IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            serializer = self.serializer_class(data=request.data)
            req_body = None
            if serializer.is_valid():
                if request.user.is_staff:
                    req_body = serializer.data
                    start_date = None
                    end_date = None
                    print(serializer.data)
                    if req_body:
                        start_date = req_body.get('start_date', None)
                        end_date = req_body.get('end_date', None)
                    check_deposits.apply_async((start_date, end_date))
                    return Response({"response": "success"})
                else:
                    return Response({"response": "You do not have permission to perform this action."})
        except Exception as e:
            return Response({"response": f"Failed due to {e}"})



class AuthorizeDepositsAPI(APIView):
    serializer_class = AuthorizeDepositsSerializer
    permission_classes = [IsNotAPIUser, IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            serializer = self.serializer_class(data=request.data)
            req_body = None
            if serializer.is_valid():
                if request.user.is_staff:
                    req_body = serializer.data
                    start_date = None
                    end_date = None
                    if req_body:
                        start_date = req_body.get('start_date', None)
                        end_date = req_body.get('end_date', None)
                    authorize_deposits.apply_async((start_date, end_date))
                    return Response({"response": "success"})
                else:
                    return Response({"response": "You do not have permission to perform this action."})
        except Exception as e:
            return Response({"response": f"Failed due to {e}"})


class CheckRefundsAPI(APIView):
    serializer_class = CheckRefundsSerializer
    permission_classes = [IsNotAPIUser, IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            serializer = self.serializer_class(data=request.data)
            req_body = None
            if serializer.is_valid():
                if request.user.is_staff:
                    req_body = serializer.data
                    start_date = None
                    end_date = None
                    print(serializer.data)
                    if req_body:
                        start_date = req_body.get('start_date', None)
                        end_date = req_body.get('end_date', None)
                    check_refunds.apply_async((start_date, end_date))
                    return Response({"response": "success"})
                else:
                    return Response({"response": "You do not have permission to perform this action."})
        except Exception as e:
            return Response({"response": f"Failed due to {e}"})


class GetChargerByAmountAPI(APIView):

    serializer_class = GetChargesByAmountAPISerializer
    permission_classes = [IsNotAPIUser, IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        try:
            if serializer.is_valid():
                amount = serializer.data.get('amount', None)
                amount = float(amount)
                origin_country = serializer.data.get('origin_country', None)
                destination_country = serializer.data.get('destination_country', None)
                if not amount or amount < 0:
                    return Response({"response": "Missing or invalid amount !"}, status=status.HTTP_204_NO_CONTENT)
                if not origin_country:
                    return Response({"response": "Missing or invalid origin country !"}, status=status.HTTP_204_NO_CONTENT)
                if not destination_country:
                    return Response({"response": "Missing or invalid destination country !"}, status=status.HTTP_204_NO_CONTENT)
                partner_origin_country = Country.objects.filter(iso_code=origin_country).first()
                partner_dest_country = Country.objects.filter(iso_code=destination_country).first()

                ## Query ExchangeRateTiers
                if partner_origin_country and partner_dest_country:
                    exchange_ratetiers = ExchangeRateTier.objects.filter(
                        country_origin=partner_origin_country,
                        country_destination=partner_dest_country
                        ).select_related("country_origin", "country_destination")
                    if exchange_ratetiers:
                        delivery_methods = list()
                        low = None
                        max = None
                        bottom_amounts = list()
                        for exch_rate_tier in exchange_ratetiers:
                            bottom_amounts.append(exch_rate_tier.bottom_amount)
                        bottom_amounts = sorted(bottom_amounts)
                        for item in bottom_amounts:
                            if amount >= float(item):
                                low = item
                            if amount < float(item):
                                max = item
                                break
                        if not max:
                            max = bottom_amounts[-1]
                        exchange_ratetier = ExchangeRateTier.objects.filter(
                            bottom_amount=low,
                            country_origin=partner_origin_country,
                            country_destination=partner_dest_country).select_related("country_origin", "country_destination").first()
                        if exchange_ratetier:
                            for item in exchange_ratetier.collect_transaction_method_fees:
                                item.pop('icon_url', None)
                                delivery_methods.append(item)

                        if  delivery_methods and exchange_ratetier.applicable_rate:
                            rate = float(exchange_ratetier.applicable_rate)
                            return Response({
                                "response":{
                                    "min":low,
                                    "max": max,
                                    "delivery_methods": delivery_methods,
                                    "rate": str(rate),
                                    "country_origin": exchange_ratetier.country_origin.name,
                                    "country_destination" : exchange_ratetier.country_destination.name,
                                    "distribution_percentage": exchange_ratetier.distribution_percentage,
                                    "profit_margin_percentage": exchange_ratetier.profit_margin_percentage,
                                    "destination_currency_uuid": str(exchange_ratetier.country_destination.default_currency.uuid)
                                }
                            }, status=status.HTTP_200_OK)
                        else:
                            return Response({"response":"No Entries found for this request"}, status=status.HTTP_204_NO_CONTENT)
                    else:
                        return Response({"response":"No Entries found for this request"}, status=status.HTTP_204_NO_CONTENT)
                else:
                    return Response({"response": "Origin-->Destination country combo not available"}, status=status.HTTP_204_NO_CONTENT)
            else:
                return Response({"response": "Missing request body!"}, status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response({"response": f"Error occured {e}"}, status=status.HTTP_204_NO_CONTENT)


class GetDestinationCountriesAPI(APIView):
    serializer_class = GetDestinationCountriesSerializer
    permission_classes = [IsNotAPIUser, IsAuthenticated]
    def post(self, request, *args, **kwargs):
        req_body = self.serializer_class(data=request.data)
        if req_body.is_valid():
            req_body = req_body.data
            origin_country = req_body.get('origin_country', None)
            partner_origin_country = Country.objects.filter(iso_code=origin_country).first()
            if origin_country and partner_origin_country:
                exchange_ratetiers = ExchangeRateTier.objects.filter(country_origin=partner_origin_country, bottom_amount=1).select_related("country_destination")
                if exchange_ratetiers:
                    response = list()
                    for exch_ratetier in exchange_ratetiers:
                        data = {}
                        data['iso_code'] = exch_ratetier.country_destination.iso_code
                        is_active = False
                        destination_country = exch_ratetier.country_destination
                        partners = Partner.objects.filter(country=destination_country, status=PartnerStatus.active)
                        if partners and destination_country.enabled_as_destination:
                            is_active = True
                        data['is_active'] = is_active
                        data['name'] = destination_country.name
                        data['currency_code'] = destination_country.default_currency.sign
                        data['currency_sign'] = destination_country.default_currency.short_sign
                        response.append(data)
                    return Response({'response':response})
                else:
                    return Response({"response": "No available destination countries found"}, status=status.HTTP_204_NO_CONTENT)
            else:
                return Response({"response": "Missing or invalid origin country !"}, status=status.HTTP_204_NO_CONTENT)

        else:
            return Response({"response": "Missing request body!"}, status=status.HTTP_204_NO_CONTENT)


class bemosenderrrAPI(APIView):
    permission_classes = [IsAuthenticated, IsAPIUser | IsAdminUser]
    serializer_class = bemosenderrrAPISerializer
    def post(self, request, *args, **kwargs):
        try:
            serializer = self.serializer_class(data=request.data)
            if serializer.is_valid():
                return bemosenderrr_api(request, dict(serializer.validated_data))
            else:
                return Response({"response": "Missing or invalid request body!"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"response": "Missing or invalid request body!"}, status=status.HTTP_400_BAD_REQUEST)


from bemosenderrr.utils.email_verification import send_email, verify_token, verify_view


class SendEmailVerificationAPI(APIView):

    permission_classes = [IsAuthenticated, IsNotAPIUser]
    serializer_class = SendEmailConfirmationSerializer

    def post(self, request, *args, **kwargs):
        try:
            serializer = self.serializer_class(data=request.data)
            if serializer.is_valid():
                user_id = serializer.data.get('user_id', None)
                email = serializer.data.get('email', None)
                user = User.objects.get(username=user_id)
                user.email = email
                try:
                    if not user.first_name or not user.last_name:
                        params = {
                            "id": str(user.username)
                        }
                        query = """
                                query MyQuery($input: ID!) {
                                    getUser(id: $input) {
                                        profileID
                                    }
                                }
                                """
                        client = make_client()
                        response_user = client.execute(gql(query), variable_values=json.dumps({'input': params['id']}))
                        profile_id = response_user.get('getUser', None).get('profileID')
                        params = {
                                    "id": str(profile_id)
                                }
                        query = """
                                query GetProfile($input: ID!) {
                                    getProfile(id: $input) {
                                        first_name last_name
                                    }
                                }
                                """
                        response_profile = client.execute(gql(query), variable_values=json.dumps({'input': params['id']}))
                        user.first_name = response_profile.get("getProfile", None).get("first_name", None)
                        user.last_name = response_profile.get("getProfile", None).get("last_name", None)
                except Exception as e:
                    print('EXCEPTION CAUGHT IN SENDING EMAIL CONFIRMATION', e)
                    return Response({"response":"ERROR OCCURED IN SENDING EMAIL CONFIRMATION"}, status=status.HTTP_400_BAD_REQUEST)
                user.save()
                #user.is_active = False
                try:
                    send_email(user)
                    return Response({'response':'success'}, status=status.HTTP_200_OK)
                except:
                    return Response({"response":"Failed"}, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({"response":"REQUEST DATA MISSING!"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"response": f"ERROR OCCURED IN SENDING EMAIL CONFIRMATION {e}"}, status=status.HTTP_400_BAD_REQUEST)


@verify_view
def confirm_email(request, token):
    token = str(token).replace("b'", "").replace("'", "")
    success, user = verify_token(token)
    print(user)
    if success:
        previous_user_status = sync_email_verification(user)
        print("Previous user status ", previous_user_status)
        if previous_user_status == "ACTIVE":
            #TODO might check if the user is migrated or not
            cognito_client = boto3.client(
                    region_name="us-west-1",
                    service_name='cognito-idp',
                )
            response = cognito_client.admin_get_user(
                                UserPoolId=settings.CONFIG.get('COGNITO_USER_POOL', None),
                                Username=user.phone_number
                            )
            user_attributes = response.get('UserAttributes', None)
            nickname = None
            if user_attributes:
                for attr in user_attributes:
                    if attr.get('Name', None) == "nickname":
                        nickname = attr.get('Value', None)
                        break

            if not nickname:
                print("User didn't confirm his email yet and is not a migrated user")
                send_welcome_email(user=user)
        else:
            print("User has just signed up")

    print(success)
    return render(request, 'email/email_confirmation.html', context={'user':user, 'success':success})
    #return HttpResponse(f'Account verified, {user.username}' if success else 'Invalid token')


def send_welcome_email(user=None):
    data = {
        "user_first_name": user.first_name
    }
    if str(user.locale).lower() == "fr":
        html_message = render_to_string(os.path.join(os.getcwd(), 'bemosenderrr','templates', 'email', 'account_welcome_email_fr.html'), data)
        subject = "Bienvenue chez bemosenderrr!"
    else:
        html_message = render_to_string(os.path.join(os.getcwd(), 'bemosenderrr','templates', 'email', 'account_welcome_email_en.html'), data)
        subject = "Welcome to bemosenderrr!"
    email = EmailMultiAlternatives(
                subject,
                "",
                str(settings.SERVER_EMAIL),
                [user.email],
    )
    email.attach_alternative(html_message, 'text/html')
    email.content_subtype = "html"
    result = email.send(fail_silently=True)
    return result


class CancelGlobalTransactionAPI(APIView):
    permission_classes = [IsAuthenticated, IsNotAPIUser]
    serializer_class = CancelGlobalTransactionSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            uuid = serializer.data.get('uuid', None)
            gl_tx_status = serializer.data.get('status', None)
            response = {}
            try:
                if uuid and gl_tx_status:
                    instance = GlobalTransaction.objects.filter(uuid=uuid, user=request.user).first()
                    if instance:
                        collect_transactions = instance.collect_transactions.all()
                        if instance.status not in [GlobalTransactionStatus.success, GlobalTransactionStatus.funding_error, GlobalTransactionStatus.blocked, GlobalTransactionStatus.refunded,
                                GlobalTransactionStatus.canceled, GlobalTransactionStatus.refundtransaction_in_progress, GlobalTransactionStatus.refunded_error, GlobalTransactionStatus.refunded]:
                            logger.info('Globaltransaction status not final !')
                            if instance.status in  [GlobalTransactionStatus.fundtransaction_in_progress, GlobalTransactionStatus.new]:
                                instance.status = GlobalTransactionStatus.canceled
                                instance.save()
                                return Response({"response":"Cancelling Accepted fundtransaction_in_progress"}, status=status.HTTP_200_OK)
                            if collect_transactions:
                                for collect_operation in collect_transactions:
                                    print(collect_operation)
                                    # TODO might check if some collect transactions are succesful
                                    if collect_operation.status not in [CollectTransactionStatus.canceled, CollectTransactionStatus.blocked, CollectTransactionStatus.on_hold,
                                            CollectTransactionStatus.rejected, CollectTransactionStatus.aml_blocked, CollectTransactionStatus.error, CollectTransactionStatus.not_found, CollectTransactionStatus.collected]:
                                        tasks = PeriodicTasksEntry.objects.filter(name=f'checking {collect_operation.partner} collect of {instance.user} {instance.uuid}')
                                        if tasks:
                                            for task in tasks:
                                                task.delete()
                                        collect_operation.cancel.apply_async((collect_operation.uuid,))
                                return Response({"response":"Cancelling Accepted collecttransaction_in_progress"}, status=status.HTTP_200_OK)
                            else:
                                return Response({"response":"Collect Transactions not found !"}, status=status.HTTP_400_BAD_REQUEST)
                        else:
                            return Response({"response":f"GlobalTransaction status in a final state ! {instance.status}"}, status=status.HTTP_400_BAD_REQUEST)
                    else:
                        return Response({"response":"No global transaction found !"}, status=status.HTTP_400_BAD_REQUEST)
                else:
                    return Response({"response":"UUID OR STATUS MISSING"}, status=status.HTTP_400_BAD_REQUEST)

            except Exception as e:
                return Response({"response":f"Error occured {e}"}, status=status.HTTP_400_BAD_REQUEST)


class GetUserMaxTransactionValue(APIView):
    serializer_class = GetUserMaxTransactionValueSerializer
    permission_classes = [IsNotAPIUser, IsAuthenticated]

    def post(self, request, *args, **kwargs):
        req_body = self.serializer_class(data=request.data)
        try:
            if req_body.is_valid():
                if req_body.data and req_body.data.get("kyc_level", None) and req_body.data.get("origin_currency", None):
                    kyc_level = req_body.data.get("kyc_level", None)
                    origin_currency = req_body.data.get("origin_currency", None)
                    tx_cumul_operation = TxLimitCumulOperations()
                    tx_cumul_operation.on_reset_limit(user=request.user)
                    last_tx_limit_cumul = TxLimitCumul.objects.filter(user=request.user).order_by("-created_at").first()
                    user_tier = UserTier.objects.filter(level=str(kyc_level)).first()
                    max_limits = {
                        "tx_max": str(user_tier.tx_max.get(origin_currency, None)),
                        "monthly_max": user_tier.monthly_max.get(origin_currency, None),
                        "quarterly_max": user_tier.quarterly_max.get(origin_currency, None),
                        "yearly_max": user_tier.yearly_max.get(origin_currency, None)
                    }
                    if last_tx_limit_cumul:
                        logger.info(last_tx_limit_cumul)
                        limit_1_month = float(last_tx_limit_cumul.limit_1_month)
                        limit_3_month = float(last_tx_limit_cumul.limit_3_month)
                        limit_12_month = float(last_tx_limit_cumul.limit_12_month)
                        logger.info('....')
                        max_limits['monthly_max'] = str(float(user_tier.monthly_max.get(origin_currency, None)) - limit_1_month)
                        max_limits['quarterly_max'] = str(float(user_tier.quarterly_max.get(origin_currency, None)) - limit_3_month)
                        max_limits['yearly_max'] = str(float(user_tier.yearly_max.get(origin_currency, None)) - limit_12_month)

                    return Response(max_limits, status=status.HTTP_200_OK)
            else:
                return Response({"response": "Request body missing or invalid"}, status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            logger.info(e.args)
            return Response({"response": "Request body missing or invalid"}, status=status.HTTP_204_NO_CONTENT)


@api_view(http_method_names=['GET'])
@authentication_classes([])
@permission_classes([])
def get_origin_countries(request):
    origin_countries = Country.objects.filter(enabled_as_origin=True, active=True)
    response = []
    if origin_countries:
        for country in origin_countries:
            data = {}
            data['name'] = country.name
            data['iso_code'] = country.iso_code
            response.append(data)
        return Response(response, status=status.HTTP_200_OK)
    else:
        return Response(response, status=status.HTTP_204_NO_CONTENT)


@api_view(http_method_names=['POST'])
def test_sns_push(request):
    if request.data:
        req_data = request.data
        global_tx_uuid = req_data.get('global_tx_uuid', None)
        global_tx = GlobalTransaction.objects.filter(uuid=global_tx_uuid).first()
        user_snapshot = GlobalTransaction.objects.filter(user=global_tx.user).last().user_snapshot
        type = req_data.get('type', None)
        data = req_data.get('data', None)
        error = req_data.get('error', None)
        new_user_tier_level = req_data.get('new_user_tier_level', None)
        old_user_tier_level = req_data.get('old_user_tier_level', None)
        user = User.objects.filter(uuid=req_data.get('user', None)).first()
        ios_token = req_data.get('fcm_token', None)
        print(user)
        if user and data and type:
            pinpoint_service = PinpointWrapper()#SNSNotificationService()
            if ios_token:
                response = pinpoint_service.send_push_notifications_and_data(status=global_tx.status, user_snapshot=user_snapshot, user=user, data=data,type=type,global_tx_uuid=global_tx_uuid, error=error,
                new_user_tier_level=new_user_tier_level, old_user_tier_level=old_user_tier_level, fcm_token=ios_token)
            else:
                response = pinpoint_service.send_push_notifications_and_data(status=global_tx.status, user_snapshot=user_snapshot, user=user, data=data,type=type,global_tx_uuid=global_tx_uuid, error=error,
                    new_user_tier_level=new_user_tier_level, old_user_tier_level=old_user_tier_level)
            return Response({"response":response})
        else:
            return Response({"response":f"Something wrong ! User:({user}) | Data: ({data}) | Type: ({type})"})
    else:
        return Response({"response":"Request body missing !!"})


@api_view(http_method_names=['POST'])
def test_sns_publish_phonenumber(request):
    if request.data:
        req_data = request.data
        phone_number = req_data.get("phone_number", None) # Can be a list of string or a string
        message = req_data.get("message", None) # string
        origination_number = req_data.get("origination_number", None)
        if phone_number and message:
            pinpoint_service = PinpointWrapper()#SNSNotificationService()
            response = pinpoint_service.send_sms(destination_number=phone_number, origination_number=origination_number, message=message)
            return Response({"response":response})
        else:
            return Response({"response":"Missing phone or message !"})
    else:
        return Response({"response":"Request body missing !!"})


class RegisterUserDevice(APIView):

    permission_classes = [IsNotAPIUser, IsAuthenticated]
    serializer_class = RegisterUserDeviceSerializer

    def post(self, request, *args, **kwargs):
        request_data = self.serializer_class(data=request.data)
        try:
            if request_data.is_valid():
                request_data = request_data.data
                user = request.user
                device_type = request_data.get('device_type', None)
                device_token = request_data.get('device_token', None)
                app_version = request_data.get('app_version', None)
                time_zone = request_data.get('time_zone', None)
                device_data = request_data.get('device_data', None)
                gcm_senderrid = request_data.get('gcm_senderrid', None)
                app_identifier = request_data.get('app_identifier', None)
                installation_id = request_data.get('installation_id', None)
                last_user_token = None
                if device_type == 'android' and device_token and app_version:
                    last_user_token = UserToken.objects.filter(device_type="android", user=user).first()
                elif device_type == 'ios' and device_token and app_version:
                    last_user_token = UserToken.objects.filter(device_type="ios", user=user).first()
                elif str(device_type) not in ['ios', 'android'] or not device_token or not app_version:
                    return Response({"response": "Missing or invalid data !"}, status=status.HTTP_400_BAD_REQUEST)
                if last_user_token:
                    last_user_token.device_token = device_token
                    last_user_token.app_version = app_version
                    last_user_token.time_zone = time_zone
                    last_user_token.gcm_senderrid = gcm_senderrid
                    last_user_token.device_data = device_data
                    last_user_token.app_identifier = app_identifier
                    last_user_token.installation_id = installation_id
                    last_user_token.save()
                elif not last_user_token and str(device_type).lower() in ['ios', 'android']:
                    user_token = UserToken.objects.create(
                        user=user,
                        device_token=device_token,
                        device_type=device_type,
                        app_version=app_version,
                        time_zone=time_zone,
                        gcm_senderrid=gcm_senderrid,
                        device_data=device_data,
                        app_identifier=app_identifier,
                        installation_id=installation_id
                    )
                else:
                    return Response({"response": "Missing or invalid data !"}, status=status.HTTP_400_BAD_REQUEST)
                return Response({"response": "succes"}, status=status.HTTP_200_OK)
            else:
                return Response({"response": "Missing or invalid data !"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"response": f"Error occured {e}"}, status=status.HTTP_400_BAD_REQUEST)



@api_view(http_method_names=['POST'])
@authentication_classes([])
@permission_classes([])
def initiate_auth(request):
    if request.data:
        req_data = request.data
        username = req_data.get('username', None)
        password = req_data.get('password', None)
        if username and password:
            try:
                client = boto3.client(
                    region_name="us-west-1",
                    service_name='cognito-idp'
                )
                response = client.initiate_auth(
                    ClientId=settings.CONFIG.get("COGNITO_CLIENT_ID", None),
                    AuthFlow='USER_PASSWORD_AUTH',
                    AuthParameters={
                        'USERNAME': username,
                        'PASSWORD': password
                    }
                )
                return Response(response, status=200)
            except Exception as e:
                print("USER NOT FOUND !", e)
                print("This will attempt to trigger UserMigration lambda")
                return Response({"data": str(e)}, status=400)
        else:
            return Response({"data": "Failed to sign in"}, status=400)


class GetChargesByAmountWebsiteAPI(APIView):
    permission_classes = [IsNotAPIUser, IsAuthenticated]
    serializer_class  = GetChargesByAmountForWebsiteSerializer
    __doc__ = _("""
    API endpoint that gets charges by amount for the available and filtered countries(For the bemosenderrr website)
    """)
    def post(self, request, *args, **kwargs):
        try:
            req_data = request.data
            serializer = self.serializer_class(data=request.data)
            if serializer.is_valid(raise_exception=True):
                amount = serializer.data.get('amount', None)
                origin_country_iso_code = serializer.validated_data.get('originCountryCode')
                destination_country_iso_code = serializer.data.get('destinationCountryCode', None)
                options = serializer.data.get('options', None)
                response = {}
                if amount:
                    active_partners = Partner.objects.filter(status=PartnerStatus.active, type=PartnerType.collect)
                    country_pairs = list()
                    for partner in active_partners:
                        exchange_rate = PartnerExchangeRate.objects.get(partner=partner)
                        country_pairs.append(f"{exchange_rate.country_origin.iso_code}_{exchange_rate.country_destination.iso_code}")
                    country_pairs = list(set(country_pairs))
                    if amount:
                        response['result'] = {}
                        #response['result']['resultCode'] = "1000"
                        response['result']['charges'] = {}
                        if origin_country_iso_code and destination_country_iso_code:
                            country_pairs = [str(str(origin_country_iso_code).upper() + "_" + str(destination_country_iso_code).upper())]
                        for country_pair in country_pairs:
                            print("Current country pair", country_pair)
                            country_pair = str(country_pair).upper()
                            destination_country = Country.objects.get(iso_code=str(country_pair).split('_')[1])
                            origin_country = Country.objects.get(iso_code=str(country_pair).split('_')[0])
                            response['result']['charges'][country_pair] = {}
                            response['result']['charges'][country_pair]['partners'] = {}
                            partners = Partner.objects.filter(country=destination_country, status=PartnerStatus.active)
                            for partner in partners:
                                partner_name = str(partner.name).lower()
                                response['result']['charges'][country_pair]['partners'][partner_name] = {}
                                response['result']['charges'][country_pair]['partners'][partner_name]['id'] = partner.name
                                response['result']['charges'][country_pair]['partners'][partner_name]['name'] = partner.display_name
                                response['result']['charges'][country_pair]['partners'][partner_name]['group'] = partner.api_config['group']
                                response['result']['charges'][country_pair]['partners'][partner_name]['logos'] = []
                                img_urls = partner.api_config['img_urls']
                                for img_url in img_urls:
                                    response['result']['charges'][country_pair]['partners'][partner_name]['logos'].append(list(img_url.values())[0])
                            response['result']['charges'][country_pair]['charges'] = {}
                            response['result']['charges'][country_pair]['charges']['fees'] = {}
                            user_tiers = UserTier.objects.all()
                            kyc_level = "0"
                            for user_tier in user_tiers:
                                if int(kyc_level) <= int(user_tier.level):
                                    kyc_level = user_tier.level
                            max_user_tier = UserTier.objects.filter(level=kyc_level).first()
                            response['result']['maxTxAmounts'] = max_user_tier.tx_max
                            #response['result']['charges'][country_pair]['max_tier_tx_limits'] = max_user_tier.tx_max[origin_country.default_currency.iso_code] # Value of biggest kyc level daily tx max TODO Removed!
                            exchange_rate_tiers = ExchangeRateTier.objects.filter(country_origin=origin_country, country_destination=destination_country)
                            low = None
                            max = None
                            bottom_amounts = list()
                            for exch_rate_tier in exchange_rate_tiers:
                                bottom_amounts.append(exch_rate_tier.bottom_amount)
                            bottom_amounts = sorted(bottom_amounts)
                            if options and options.get('is_destination_amount', False):
                                temp_exch_rate_tier = ExchangeRateTier.objects.filter(country_origin=origin_country, country_destination=destination_country).first()
                                rate_temp = temp_exch_rate_tier.applicable_rate
                                amount = float(amount) / float(rate_temp)
                            for item in bottom_amounts:
                                if amount >= float(item):
                                    low = item
                                if amount < float(item):
                                    max = item
                                    break
                            if not max:
                                max = bottom_amounts[-1]
                            exchange_ratetier = ExchangeRateTier.objects.filter(bottom_amount=low, country_origin=origin_country, country_destination=destination_country).first()
                            collect_methods = exchange_ratetier.collect_transaction_method_fees
                            for collect_method in collect_methods:
                                if "cash" in str(collect_method).lower():
                                    response['result']['charges'][country_pair]['charges']['fees']['cashpickup'] = float(collect_method['fee'])
                                else:
                                    response['result']['charges'][country_pair]['charges']['fees'][collect_method['name']] = float(collect_method['fee'])
                            response['result']['charges'][country_pair]['charges']['rate'] = float(exchange_ratetier.applicable_rate)
                            response['result']['charges'][country_pair]['charges']['min'] = low
                            response['result']['charges'][country_pair]['charges']['max'] = max
                            response['result']['charges'][country_pair]['countryOrigin'] = {}
                            response['result']['charges'][country_pair]['countryDestination'] = {}
                            response['result']['charges'][country_pair]['currencyOrigin'] = {}
                            response['result']['charges'][country_pair]['currencyDestination'] = {}
                            response['result']['charges'][country_pair]['countryOrigin']['name'] = str(origin_country.name).upper() #TODO change this
                            response['result']['charges'][country_pair]['countryOrigin']['code'] = origin_country.iso_code
                            response['result']['charges'][country_pair]['countryOrigin']['codeLong'] = origin_country.alpha_3_code
                            response['result']['charges'][country_pair]['countryDestination']['name'] = destination_country.name
                            response['result']['charges'][country_pair]['countryDestination']['code'] = destination_country.iso_code
                            response['result']['charges'][country_pair]['countryDestination']['codeLong'] = destination_country.alpha_3_code
                            response['result']['charges'][country_pair]['currencyOrigin']['code'] = origin_country.default_currency.iso_code
                            response['result']['charges'][country_pair]['currencyOrigin']['sign'] = origin_country.default_currency.sign
                            response['result']['charges'][country_pair]['currencyOrigin']['shortSign'] = origin_country.default_currency.short_sign
                            response['result']['charges'][country_pair]['currencyDestination']['code'] = destination_country.default_currency.iso_code
                            response['result']['charges'][country_pair]['currencyDestination']['sign'] = destination_country.default_currency.sign
                            response['result']['charges'][country_pair]['currencyDestination']['shortSign'] = destination_country.default_currency.short_sign
                return Response(response, status=status.HTTP_200_OK)
        except Exception as e:
            print("Exception caught in GetChargesByAmount", e)
            return Response({"response": f"Error occured {e}"}, status=status.HTTP_400_BAD_REQUEST)


class InitAPIView(PicklesAPIView):
    """Shows init configs params"""
    authentication_classes = []
    permission_classes = []


class FlinksAPIView(RetrieveAPIView):
    """Shows generated flinks iframe url"""
    authentication_classes = []
    permission_classes = []
    serializer_class = FlinksIframURLSerializer

    def retrieve(self, request, *args, **kwargs):
        country = self.request.query_params.get('country', 'CA')
        language = self.request.query_params.get('language', 'en')
        terms_url = Pickle.objects.get(name='general_conditions_url').value
        if country == 'CA':
            terms_url = terms_url[country][language]
        else:
            terms_url = terms_url['default'][language]
        if country == 'US':
            url = settings.FLINKS_US_BASE_URL
        else:
            url = settings.FLINKS_CA_BASE_URL
        if language == 'fr':
            url = f"{url}&language=fr"
        url = f"{url}&termsNoCheckbox=true&customerName=bemosenderrr&termsUrl={urllib.parse.quote(terms_url, safe='')}"
        serializer = self.get_serializer(data={'iframe_url': url})
        serializer.is_valid(True)
        return Response(serializer.data)


class DisableUserAPI(APIView):

    permission_classes = [IsNotAPIUser, IsAuthenticated]
    serializer_class  = DisableUserSerializer

    def post(self, request, *args, **kwargs):
        try:
            serializer = self.serializer_class(data=request.data)
            if serializer.is_valid():
                client = boto3.client(
                    region_name="us-west-1",
                    service_name='cognito-idp',
                )
                user = User.objects.filter(username=serializer.validated_data.get('user_id', None)).first()
                if user == request.user or request.user.is_staff:
                    phone_number = None
                    if user:
                        phone_number = user.phone_number
                    else:
                        return Response({"response": "User does not exist!"}, status=400)
                    if phone_number:
                        response = client.admin_disable_user(
                            UserPoolId=settings.CONFIG.get('COGNITO_USER_POOL', None),
                            Username=phone_number
                        )
                        print(response)
                        if request.user.is_staff:
                            user.is_active = False
                            user.save()
                            data = {
                                "user_first_name": user.first_name,
                                "user_last_name": user.last_name,
                                "user_phone_number": user.phone_number
                            }
                            if str(user.locale).lower() == "fr":
                                html_message = render_to_string(os.path.join(os.getcwd(), 'bemosenderrr','templates', 'email', 'account_blocked_email_fr.html'), data)
                                subject = "Compte suspendu"
                            else:
                                html_message = render_to_string(os.path.join(os.getcwd(), 'bemosenderrr','templates', 'email', 'account_blocked_email_en.html'), data)
                                subject = "Account Suspended"
                            email = EmailMultiAlternatives(
                                        subject,
                                        "",
                                        str(settings.SERVER_EMAIL),
                                        [user.email],
                            )
                            email.attach_alternative(html_message, 'text/html')
                            email.content_subtype = "html"
                            result = email.send(fail_silently=True)
                            print("Email result", result)
                        return Response({"response": "success"}, status=200)
                    else:
                        return Response({"response": "User has no phone number !"}, status=400)
                else:
                    return Response({"response": "Unauthorized to do this call!"}, status=403)
        except Exception as e:
            return Response({"response": f"An ERROR occured {e}"}, status=500)


class EnableUserAPI(APIView, APIUserPermissionMixins):
    permission_classes = [IsNotAPIUser, IsAuthenticated]
    serializer_class  = EnableUserSerializer

    def post(self, request, *args, **kwargs):
        try:
            serializer = self.serializer_class(data=request.data)
            if serializer.is_valid():
                if not request.user.is_staff:
                    return Response({"response": "Unauthorized to do this call!"}, status=403)
                client = boto3.client(
                    region_name="us-west-1",
                    service_name='cognito-idp',
                )
                user = User.objects.filter(username=serializer.validated_data.get('user_id', None)).first()
                if user:
                    phone_number = user.phone_number
                    if phone_number:
                        user.is_active = True
                        user.save()
                        response = client.admin_enable_user(
                            UserPoolId=settings.CONFIG.get('COGNITO_USER_POOL', None),
                            Username=phone_number
                        )
                        print(response)
                        return Response({"response": "success"}, status=200)
                    else:
                        return Response({"response": "User has no phone number !"}, status=400)
                else:
                    return Response({"response": "No such user found!"}, status=403)
        except Exception as e:
            return Response({"response": f"An ERROR occured {e}"}, status=500)


class GetMobileNetworksAvailibilitiesAPI(APIView, APIUserPermissionMixins):

    permission_classes = [IsNotAPIUser, IsAuthenticated]
    serializer_class  = GetMobileNetworksAvailibilitiesSerializer

    def post(self, request, *args, **kwargs):
        try:
            serializer = self.serializer_class(data=request.data)
            if serializer.is_valid():
                destination_country = serializer.validated_data.get('destination_country', None)
                print(destination_country)
                country = Country.objects.get(iso_code=destination_country)
                mobile_networks = MobileNetworkAvailability.objects.filter(country=country)
                response = {}
                response['networks'] = []
                if mobile_networks:

                    for mobile_network in mobile_networks:
                        name_en = mobile_network.mobile_network.display_name_en
                        name_fr = mobile_network.mobile_network.display_name_fr
                        active = "false"
                        if mobile_network.active:
                            active = "true"
                        else:
                            active = "false"
                        response['networks'].append(
                            {
                                "active": active,
                                "names": [
                                    {
                                        "lang": "en",
                                        "name": name_en
                                    },
                                    {
                                        "lang": "fr",
                                        "name": name_fr
                                    }
                                ]
                            }
                        )
                    return Response(response, status=200)
                else:
                    return Response(response, status=200)
            else:
                Response({"response": f"Missing destination_country"}, status=400)
        except Exception as e:
            return Response({"response": f"An ERROR occured {e}"}, status=500)


@api_view(http_method_names=['POST'])
def apaylo_view(request):
    if not request.user.is_staff:
        return Response({"response": "Unauthorized to do this call"}, status=403)
    apaylo = Partner.objects.filter(name='Apaylo').first()
    api_config = apaylo.api_config
    credentials = apaylo.api_user.credentials
    api_config['credentials'] = credentials
    apaylo_service = ApayloService()
    service = request.data.get('service', None)
    start_date = request.data.get('start_date', None)
    end_date = request.data.get('end_date', None)
    ref_number = request.data.get('ref_number', None)
    security_answer = request.data.get('security_answer', None)
    hash_salt = request.data.get('hash_salt', None)
    search_results = get_transfer = auth_transfer = complete_transfer = None
    if service == "search":
        search_results = apaylo_service.search_incoming_transfers(api_config=api_config, start_date=start_date, end_date=end_date)
    if service == "get":
        get_transfer = apaylo_service.get_incoming_transfers(api_config=api_config, ref_number=ref_number)
    if service == "auth":
        auth_transfer = apaylo_service.authenticate_transfer(api_config=api_config, ref_number=ref_number, security_answer=security_answer,hash_salt=hash_salt)
    if service == "comp":
        complete_transfer = apaylo_service.complete_transfer(api_config=api_config, ref_number=ref_number)
    #
    if search_results:
        return Response({"response": search_results[0]}, status=200)
    if get_transfer:
        return Response({"response": get_transfer[0]}, status=200)
    if auth_transfer:
        return Response({"response": auth_transfer[0]}, status=200)
    if complete_transfer:
        return Response({"response": complete_transfer[0]}, status=200)


@api_view(http_method_names=['GET'])
def test_pending_flinks_periodic_task(request):
    update_pending_sign_up_flinks()
    return Response({"response":"success"})

