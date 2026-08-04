{
    'name': 'AIDT Digital Signature (Ký Số PAdES)',
    'version': '1.0',
    'category': 'Document Management',
    'summary': 'Module Ký số điện tử PAdES & chuyển đổi PDF chuẩn Nghị định 30',
    'author': 'AIDT Team',
    'depends': ['base', 'mail', 'aidt_base', 'aidt_org'],
    'data': [
        'security/sign_groups.xml',
        'security/ir.model.access.csv',
        'views/aidt_sign_certificate_views.xml',
        'views/res_users_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
