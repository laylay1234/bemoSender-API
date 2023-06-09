from django_filters.rest_framework import FilterSet

from bemosenderrr.models import CustomField, User


class UserFilter(FilterSet):

    class Meta:
        model = User
        fields = {
            # 'first_name': ['exact', 'regex', 'icontains', 'in'],
            # 'last_name': ['exact', 'regex', 'icontains', 'in'],
            'email': ['exact', 'regex', 'icontains', 'in'],
            'username': ['exact', 'regex', 'icontains', 'in'],
            'last_login': ['lte', 'gte', 'range']
        }


class CustomFieldFilter(FilterSet):

    class Meta:
        model = CustomField
        fields = {
            'key': ['exact', 'regex', 'icontains', 'in'],
            'value': ['exact', 'regex', 'icontains', 'in'],
            'content_type': ['exact', 'in'],
        }
