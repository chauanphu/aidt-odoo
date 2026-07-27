from .base_provider import BaseProvider


class StaticProvider(BaseProvider):
    """Provider cho dữ liệu tĩnh, phím tắt (Shortcuts) và banner."""

    def fetch_data(self, env, widget, filter_values=None):
        action_name = widget.drilldown_action_id.name if widget.drilldown_action_id else "Truy cập nhanh"
        return {
            'type': 'shortcut',
            'widget_type': 'shortcut',
            'title': widget.name,
            'action_name': action_name,
            'action_id': widget.drilldown_action_id.id if widget.drilldown_action_id else False,
            'icon': widget.icon or 'fa-external-link',
            'model_name': widget.model_name or False
        }
