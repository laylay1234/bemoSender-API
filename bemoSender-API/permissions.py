from rest_framework import permissions
from rest_framework.permissions import IsAuthenticated, IsAdminUser


class CustomObjectPermissions(permissions.DjangoObjectPermissions):
    """
    Similar to `DjangoObjectPermissions`, but adding 'view' permissions.
    """
    perms_map = {
        'GET': ['%(app_label)s.view_%(model_name)s'],
        'OPTIONS': ['%(app_label)s.view_%(model_name)s'],
        'HEAD': ['%(app_label)s.view_%(model_name)s'],
        'POST': ['%(app_label)s.add_%(model_name)s'],
        'PUT': ['%(app_label)s.change_%(model_name)s'],
        'PATCH': ['%(app_label)s.change_%(model_name)s'],
        'DELETE': ['%(app_label)s.delete_%(model_name)s'],
    }

"""
Permission class to prevent cognito / django non staff users from using the bemosenderrr API.
"""
class IsNotAPIUser(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.user and not request.user.groups.filter(name='API USER GROUP'):
            return True
        return False

"""
Permission mixins class to add IsNotAPIUser permission class to a view.
"""
class APIUserPermissionMixins:
    def __init__(self):
        self.permission_classes = [IsAuthenticated, IsNotAPIUser]

    def get_permissions(self):
        if self.request.method in ['POST', 'DELETE', 'PATCH', 'PUT', 'GET']:
            self.permission_classes = [IsAuthenticated, IsNotAPIUser]
        return super().get_permissions()

    def check_permissions(self, request):
        print(self.get_permissions())
        for permission in self.get_permissions():
            if not permission.has_permission(request, self):
                self.permission_denied(
                    request, message=getattr(permission, 'message', None)
                )

"""
Permission class to allow API Partner Users using the bemosenderrr API
"""
class IsAPIUser(permissions.BasePermission):

    def has_permission(self, request, view):
        if request.user and request.user.groups.filter(name='API USER GROUP'):
            return True
        return False

"""
Permission mixins class to add IsAPIUser permission class to a view.
"""
class APIUserPermissionFilter():
    def __init__(self):
        self.permission_classes = [IsAuthenticated, IsAPIUser | IsAdminUser]

    def get_permissions(self):
        if self.request.method in ['POST', 'DELETE', 'GET']:
            self.permission_classes = [IsAuthenticated, IsAPIUser | IsAdminUser]
        return super().get_permissions()

    def check_permissions(self, request):
        print(self.get_permissions())
        for permission in self.get_permissions():
            if not permission.has_permission(request, self):
                self.permission_denied(
                    request, message=getattr(permission, 'message', None)
                )
