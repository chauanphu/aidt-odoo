from .base_provider import BaseProvider


class StaticProvider(BaseProvider):
    """Provider cho dữ liệu tĩnh, phím tắt (Shortcuts) và banner."""

    def fetch_data(self, env, widget, filter_values=None):
        return {
            'type': 'shortcut',
            'title': widget.name,
            'action_id': widget.drilldown_action_id.id if widget.drilldown_action_id else False
        }
