import debug_toolbar
from django.conf.urls import url
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.decorators.cache import cache_page
from django.views.generic import TemplateView
from django.views.i18n import JSONCatalog
from rest_framework.documentation import include_docs_urls
from django.conf.urls.i18n import i18n_patterns

from rest_framework.renderers import SchemaJSRenderer
from rest_framework.schemas import get_schema_view
from rest_framework_nested import routers

from bemosenderrr import views


router = routers.SimpleRouter()
router.register('send-money', views.GlobalTransactionViewSet, basename='send-money')
router.register('kyc-verify', views.KycVerificationViewSet, basename='kyc-verify')
router.register('user-bank-verify', views.UserVerificationByBankViewSet, basename='user-bank-verify')


urlpatterns = [
    url(r'^jet/', include('jet.urls', 'jet')),
    url(r'^jet/dashboard/', include('jet.dashboard.urls', 'jet-dashboard')),
    path('admin/doc/', include('django.contrib.admindocs.urls')),
    url(r'^admin/', admin.site.urls),
    url(r'^__debug__/', include(debug_toolbar.urls)),
    path("index.html", views.index,),
    path("", views.index,),
    path('v1/', include((router.urls, 'bemosenderrr'), namespace='v1')),
    re_path('^(?P<version>(v1|v2))/docs/', include_docs_urls(title="bemosenderrr API")),
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    url('^v1/rest-auth/', include('dj_rest_auth.urls')),
    path('v1/me', views.UserProfileAPI.as_view(), name='user-detail'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('openapi', get_schema_view(title="bemosenderrr", description="Exploit your data, not the planet", version="0.9.0"), name='openapi-schema'),
    url('^v1/swagger-ui/', TemplateView.as_view(template_name='swagger-ui.html', extra_context={'schema_url':'openapi-schema'}), name='swagger-ui'),
    url('^v1/redoc/', TemplateView.as_view( template_name='redoc.html', extra_context={'schema_url': 'openapi-schema'}), name='redoc'),
    path('jsi18n/', cache_page(3600, key_prefix='js18n1')(JSONCatalog.as_view()), name='javascript-catalog'),
    url(r'(?P<version>(v[0-9]|))docs/schema.js', cache_page(3600, key_prefix='js18n2')(get_schema_view(title='The bemosenderrr Platform API',
                                                                                    description="Abuse your data, not the planet",
                                                                                    version="0.2.0",
                                                                                    renderer_classes=[SchemaJSRenderer])),
        name='api-docs'),
    path('v1/user/', views.UserModelViewSet.as_view(), name="user"),
    path('v1/get-daily-account-statement/', views.get_daily_account_statement, name='get-daily-account-statement'),
    path('v1/update-rates', views.update_rates_test, name="update-rates"),
    path('v1/get-emails', views.test_gmail, name="get_emails"),
    path('v1/check-deposits', views.CheckDepositsAPI.as_view(), name="check-deposits"),
    path('v1/authorize-deposits', views.AuthorizeDepositsAPI.as_view(), name="authorize-deposits"),
    path('v1/get-charges-by-amount', views.GetChargerByAmountAPI.as_view(), name="get-charges-by-amount"),
    path('v1/get-destination-countries', views.GetDestinationCountriesAPI.as_view(), name="get-destination-countries"),
    path('v1/user-tiers', views.UserTierAPI.as_view(), name="user-tiers"),
    path('v1/bemosenderrr-api', views.bemosenderrrAPI.as_view(), name="bemosenderrr-api"),
    path('v1/email-verification/<str:token>/', views.confirm_email, name="email-verification"),
    path('v1/send-email', views.SendEmailVerificationAPI.as_view(), name="send-email"),
    path('v1/cancel-global-transaction', views.CancelGlobalTransactionAPI.as_view(), name="cancel-global-transaction"),
    path('v1/get-user-max-tx-value', views.GetUserMaxTransactionValue.as_view(), name="get-user-max-tx-value"),
    path('v1/get-origin-countries', views.get_origin_countries, name="get-origin-countries"),
    path('v1/register-device', views.RegisterUserDevice.as_view(), name="register-device"),
    path('v1/test-sms', views.test_sns_publish_phonenumber, name="test-sms"),
    path('v1/test-push', views.test_sns_push, name="test-push"),
    path('v1/sign-in', views.initiate_auth, name="sign-in"),
    path('v1/getChargesByAmount', views.GetChargesByAmountWebsiteAPI.as_view(), name="getChargesByAmount"),
    path('v1/block-user', views.DisableUserAPI.as_view(), name="block-user"),
    path('v1/enable-user', views.EnableUserAPI.as_view(), name="enable-user"),
    path('v1/get-mobile-networks', views.GetMobileNetworksAvailibilitiesAPI.as_view(), name="get-mobile-networks"),
    path('test-apaylo', views.apaylo_view, name="test-apaylo"),
    path('v1/init/', views.InitAPIView.as_view(), name='init-api'),
    path('v1/flinks/iframe', views.FlinksAPIView.as_view(), name='flinks-iframe-api'),
    path('v1/check-refunds', views.CheckRefundsAPI.as_view(), name="check-refunds"),
    path('v1/test-pending-flinks', views.test_pending_flinks_periodic_task, name="test-pending-flinks")

]

urlpatterns += router.urls


urlpatterns = i18n_patterns(path('', include(urlpatterns)), prefix_default_language=False)