{
    'name': 'AIDT Văn bản đến',
    'version': '1.0',
    'category': 'Human Resources',
    'summary': 'Quản lý văn bản đến — tiếp nhận, đăng ký, bút phê, giao việc (V-01→V-05)',
    'depends': ['aidt_org', 'aidt_dms', 'aidt_task'],
    'data': [
        'data/ir_sequence_data.xml',
        'data/ir_cron_data.xml',
        'security/ir.model.access.csv',
        'views/vanban_den_views.xml',
        'views/vanban_den_menus.xml',
        'reports/report_so_vanban_den.xml',
    ],
    'application': True,
    'sequence': 1,
    'license': 'LGPL-3',
}
