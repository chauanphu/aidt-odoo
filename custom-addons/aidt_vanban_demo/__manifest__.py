{
    'name': 'AIDT Văn bản — Dữ liệu Demo & UAT',
    'version': '1.0',
    'category': 'Human Resources',
    'summary': 'Tự động khởi tạo dữ liệu mẫu cho Kịch bản UAT (Văn bản đến, Văn bản đi, Mẫu văn bản, Nhiệm vụ)',
    'depends': ['aidt_org', 'aidt_org_demo', 'aidt_vanban_den', 'aidt_vanban_di', 'aidt_task', 'aidt_dashboard_demo'],
    'data': [
        'data/demo_templates.xml',
        'data/demo_vanban_den.xml',
        'data/demo_vanban_di.xml',
        'data/demo_tasks.xml',
        'data/demo_certs.xml',
    ],
    'installable': True,
    'license': 'LGPL-3',
}
