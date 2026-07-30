{
    'name': 'Universal Dynamic Dashboard Builder',
    'version': '19.0.1.0.0',
    'category': 'Extra Tools',
    'summary': 'No-code, metadata-driven, drag-and-drop Universal Dashboard Builder',
    'description': """
Universal Dynamic Dashboard Builder for Odoo 19.
================================================
Features:
- Metadata-driven No-code Query Engine
- Dynamic Filters & Drill-down
- Drag & Drop Responsive Canvas
- Security & ORM Whitelist Engine
- Performance Batch Loading & Caching
    """,
    'author': 'AIDT Team',
    'license': 'LGPL-3',
    'depends': ['base', 'web', 'hr', 'mail', 'aidt_org', 'aidt_dms', 'aidt_task', 'aidt_calendar'],
    'data': [
        'security/dashboard_groups.xml',
        'security/ir.model.access.csv',
        'security/dashboard_rules.xml',
        'data/dashboard_cron.xml',
        'data/dashboard_templates.xml',
        'data/dashboard_data.xml',
        'views/dashboard_views.xml',
        'views/dashboard_widget_views.xml',
        'views/dashboard_menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'aidt_dashboard_builder/static/src/style/dashboard.scss',
            'aidt_dashboard_builder/static/src/services/widget_registry.js',
            'aidt_dashboard_builder/static/src/widgets/kpi/kpi_widget.js',
            'aidt_dashboard_builder/static/src/widgets/kpi/kpi_widget.xml',
            'aidt_dashboard_builder/static/src/widgets/chart/chart_widget.js',
            'aidt_dashboard_builder/static/src/widgets/chart/chart_widget.xml',
            'aidt_dashboard_builder/static/src/widgets/table/table_widget.js',
            'aidt_dashboard_builder/static/src/widgets/table/table_widget.xml',
            'aidt_dashboard_builder/static/src/widgets/activity/activity_widget.js',
            'aidt_dashboard_builder/static/src/widgets/activity/activity_widget.xml',
            'aidt_dashboard_builder/static/src/widgets/shortcut/shortcut_widget.js',
            'aidt_dashboard_builder/static/src/widgets/shortcut/shortcut_widget.xml',
            'aidt_dashboard_builder/static/src/components/widget_library_sidebar.js',
            'aidt_dashboard_builder/static/src/components/widget_library_sidebar.xml',
            'aidt_dashboard_builder/static/src/components/dashboard_filter_bar.js',
            'aidt_dashboard_builder/static/src/components/dashboard_filter_bar.xml',
            'aidt_dashboard_builder/static/src/actions/dashboard_viewer.js',
            'aidt_dashboard_builder/static/src/actions/dashboard_viewer.xml',
        ],
    },
    'installable': True,
    'application': True,
}
