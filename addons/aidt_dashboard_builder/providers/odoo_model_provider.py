from .base_provider import BaseProvider
from ..services.query_engine import QueryEngine


class OdooModelProvider(BaseProvider):
    """Provider lấy dữ liệu từ Odoo Models thông qua ORM Query Engine."""

    def fetch_data(self, env, widget, filter_values=None):
        return QueryEngine.execute_widget_query(env, widget, filter_values)
