from django.apps import AppConfig


class CertificatesConfig(AppConfig):
    name = 'certificates'

    def ready(self):
        from . import signals  # noqa: F401
