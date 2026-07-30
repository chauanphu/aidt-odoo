{
    'name': 'AIDT Văn bản',
    'version': '1.0',
    'category': 'Human Resources',
    'summary': 'Quản lý văn bản đến & văn bản đi thống nhất',
    'depends': ['aidt_org', 'aidt_dms', 'aidt_task', 'aidt_vanban_di'],
    'data': [
        'data/ir_sequence_data.xml',
        'data/ir_cron_data.xml',
        'security/ir.model.access.csv',
        'views/vanban_den_views.xml',
        'views/vanban_den_menus.xml',
        'reports/report_so_vanban_den.xml',
        'views/unified_document_menus.xml',
    ],
    'application': True,
    'sequence': 1,
    'license': 'LGPL-3',
}
