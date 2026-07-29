{
    'name': 'AIDT Văn bản đi',
    'version': '1.0',
    'category': 'Human Resources',
    'summary': 'Quản lý văn bản đi — soạn thảo, duyệt 3 cấp, ký số, ban hành, lưu trữ',
    'depends': ['aidt_org', 'aidt_dms'],
    'data': [
        'data/ir_sequence_data.xml',
        'security/ir.model.access.csv',
        'views/vanban_di_views.xml',
        'views/vanban_di_menus.xml',
        'views/aidt_document_template_views.xml',
        'reports/report_so_vanban_di.xml',
    ],
    'application': False,
    'sequence': 2,
    'license': 'LGPL-3',
}
