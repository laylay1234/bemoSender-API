from aws_xray_sdk.core import xray_recorder
from django.utils.translation import gettext_lazy as _


class SetRemoteAddrFromForwardedFor:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request, **kwargs):
        try:
            raw_header = request.META['HTTP_X_FORWARDED_FOR']
            ip_list = raw_header.split(',')
            real_ip = ip_list[self.real_ip_index(len(ip_list))].strip()
            request.META['REMOTE_ADDR'] = real_ip
            request.META['HTTP_X_REAL_IP'] = real_ip
            segment = xray_recorder.current_segment()
            segment.put_metadata('ip', real_ip)
        except KeyError:
            pass

        return self.get_response(request)

    def real_ip_index(self, nb_ip):
        if nb_ip == 1:
            return -1
        elif nb_ip == 2:
            return -2
        elif nb_ip == 3:
            return -3
        else:
            raise PermissionError(_('Request has invalid headers.'))
