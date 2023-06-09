from rest_framework.pagination import LimitOffsetPagination


class ResultSetPagination(LimitOffsetPagination):
    default_limit = 1000
    max_limit = 10000