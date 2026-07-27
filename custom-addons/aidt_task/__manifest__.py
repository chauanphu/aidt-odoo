{
    'name': 'AIDT Nhiệm vụ',
    'version': '1.0',
    'category': 'Productivity',
    'summary': 'Theo dõi nhiệm vụ từ văn bản/ad-hoc: vòng đời, nhắc việc, '
               'báo cáo, độ mật (Nhóm 5 core, không-AI)',
    'depends': ['aidt_org', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'security/aidt_task_rules.xml',
        'data/aidt_task_cron.xml',
        'views/aidt_task_views.xml',
        'views/aidt_document_views.xml',
    ],
    'license': 'LGPL-3',
    'application': False,
}
