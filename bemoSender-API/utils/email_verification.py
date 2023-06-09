import functools
import logging
from threading import Thread
from typing import Callable

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template import Template, Context
from django.template.loader import render_to_string
from django.urls import get_resolver
from django.utils import timezone

from datetime import datetime

import jwt
from django.conf import settings
from django.contrib.auth import get_user_model


class EmailVerificationTokenGenerator:
    """
    Strategy object used to generate and check tokens for the password
    reset mechanism.
    """
    try:
        key_salt = settings.CUSTOM_SALT
    except AttributeError:
        key_salt = "django-email-verification.token"
    algorithm = None
    secret = settings.SECRET_KEY

    def make_token(self, user, expiry=None):
        """
        Return a token that can be used once to do a password reset
        for the given user.

        Args:
            user (Model): the user
            expiry (datetime): optional forced expiry date

        Returns:
             (tuple): tuple containing:
                token (str): the token
                expiry (datetime): the expiry datetime
        """
        exp = (self._now() + settings.EMAIL_TOKEN_LIFE) if expiry is None else int(expiry.timestamp())
        payload = {'email': user.email, 'exp': exp}
        return jwt.encode(payload, self.secret, algorithm='HS256'), datetime.fromtimestamp(exp)

    def check_token(self, token):
        """
        Check that a password reset token is correct.
        Args:
            token (str): the token from the url

        Returns:
            (tuple): tuple containing:
                valid (bool): True if the token is valid
                user (Model): the user model if the token is valid
        """

        try:
            payload = jwt.decode(token, self.secret, algorithms=['HS256'])
            email, exp = payload['email'], payload['exp']
            """
            if hasattr(settings, 'EMAIL_MULTI_USER') and settings.EMAIL_MULTI_USER:
                users = get_user_model().objects.filter(email=email)
            else:
            """
            users = [get_user_model().objects.filter(email=email).order_by("created_at").last()]
        except (ValueError, get_user_model().DoesNotExist, jwt.DecodeError, jwt.ExpiredSignatureError):
            return False, None

        if not len(users) or users[0] is None:
            return False, None

        return True, users[0]

    @staticmethod
    def _now():
        return datetime.now().timestamp()


default_token_generator = EmailVerificationTokenGenerator()

logger = logging.getLogger('django_email_verification')
DJANGO_EMAIL_VERIFICATION_MORE_VIEWS_ERROR = 'ERROR: more than one verify view found'
DJANGO_EMAIL_VERIFICATION_NO_VIEWS_ERROR = 'ERROR: no verify view found'
DJANGO_EMAIL_VERIFICATION_NO_PARAMETER_WARNING = 'WARNING: found verify view without parameter'


def send_email(user, thread=True, **kwargs):
    try:
        user.save()

        expiry_ = kwargs.get('expiry')
        token, expiry = default_token_generator.make_token(user, expiry_)

        senderr = _get_validated_field('EMAIL_FROM_ADDRESS')
        domain = _get_validated_field('EMAIL_PAGE_DOMAIN')
        subject = _get_validated_field('EMAIL_MAIL_SUBJECT')
        mail_plain = _get_validated_field('EMAIL_MAIL_PLAIN')
        mail_html = _get_validated_field('EMAIL_MAIL_HTML')

        args = (user, token, expiry, senderr, domain, subject, mail_plain, mail_html)
        if thread:
            t = Thread(target=send_email_thread, args=args)
            t.start()
        else:
            send_email_thread(*args)
    except AttributeError:
        raise Exception('The user model you provided is invalid')


def send_email_thread(user, token, expiry, senderr, domain, subject, mail_plain, mail_html):
    domain += '/' if not domain.endswith('/') else ''

    def has_decorator(k):
        if callable(k):
            return k.__dict__.get('django_email_verification_view_id', False)
        return False

    d = [v[0][0] for k, v in get_resolver(None).reverse_dict.items() if has_decorator(k)]
    w = [a[0] for a in d if a[1] == []]
    d = [a[0][:a[0].index('%')] for a in d if a[1] != []]

    if len(w) > 0:
        print(f'{DJANGO_EMAIL_VERIFICATION_NO_PARAMETER_WARNING}: {w}')

    if len(d) < 1:
        print(DJANGO_EMAIL_VERIFICATION_NO_VIEWS_ERROR)
        return

    if len(d) > 1:
        print(f'{DJANGO_EMAIL_VERIFICATION_MORE_VIEWS_ERROR}: {d}')
        return
    try:
        context = {'link': domain + d[0] + str(token), 'expiry': expiry, 'user': user}
    except Exception as e:
        print(e)

    subject = Template(subject).render(Context(context))

    text = render_to_string(mail_plain, context)

    html = render_to_string(mail_html, context)

    msg = EmailMultiAlternatives(subject, text, senderr, [user.email])
    msg.attach_alternative(html, 'text/html')
    msg.send()
    print(f"Sending email confirmation to user {user}")


def _get_validated_field(field, default_type=None):
    if default_type is None:
        default_type = str
    try:
        d = getattr(settings, field)
        if d == "" or d is None or not isinstance(d, default_type):
            raise AttributeError
        return d
    except AttributeError:
        raise Exception(f"Field {field} missing or invalid")


def verify_token(token):
    valid, user = default_token_generator.check_token(token)
    if valid:
        callback = _get_validated_field('EMAIL_VERIFIED_CALLBACK', default_type=Callable)
        if hasattr(user, callback.__name__):
            getattr(user, callback.__name__)()
        else:
            callback(user)
        user.last_login = timezone.now()
        user.save()
        return valid, user
    return False, None


def verify_view(func):
    func.django_email_verification_view_id = True

    @functools.wraps(func)
    def verify_function_wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return verify_function_wrapper
