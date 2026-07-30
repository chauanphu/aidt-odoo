{
    'name': 'AIDT Thể thức văn bản',
    'version': '1.0',
    'author': 'AIDT',
    'category': 'Document Management',
    'summary': 'Engine kiểm tra thể thức văn bản theo bộ luật cấu hình được (D-03/D-07/D-09)',
    'depends': ['base', 'aidt_org'],
    'external_dependencies': {'python': ['docx', 'yaml']},
    'data': [
        'security/ir.model.access.csv',
        'views/format_ruleset_views.xml',
        'views/format_check_wizard_views.xml',
        'views/format_document_views.xml',
        'data/format_ruleset_data.xml',
    ],
    'application': True,
    'license': 'LGPL-3',
}
