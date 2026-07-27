from .odoo_model_provider import OdooModelProvider
from .system_metric_provider import SystemMetricProvider
from .static_provider import StaticProvider


class ProviderRegistry:
    """Registry quản lý các Data Providers."""

    _providers = {
        'odoo_model': OdooModelProvider(),
        'system_metric': SystemMetricProvider(),
        'static': StaticProvider(),
    }

    @classmethod
    def get_provider(cls, provider_type):
        return cls._providers.get(provider_type, cls._providers['odoo_model'])
