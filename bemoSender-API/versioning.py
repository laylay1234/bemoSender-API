from rest_framework.versioning import NamespaceVersioning

class bemosenderrrVersioning(NamespaceVersioning):
    default_version = 'v1'
    allowed_versions = ['v2', 'v1']
    version_param = 'version'
