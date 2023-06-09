from rest_framework.versioning import NamespaceVersioning

class bemoSenderrVersioning(NamespaceVersioning):
    default_version = 'v1'
    allowed_versions = ['v2', 'v1']
    version_param = 'version'
