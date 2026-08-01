{
    'name': 'AIDT Tìm kiếm thông minh',
    'version': '1.0',
    'category': 'Document Management',
    'summary': 'Chỉ mục lai (vector + lexical) và tìm kiếm ngữ nghĩa trên kho văn bản '
               '(V-10 → V-14, S-11, N-12)',
    'depends': ['aidt_dms', 'aidt_org'],
    'data': [
        'security/ir.model.access.csv',
        'security/aidt_search_rules.xml',
        'data/ir_config_parameter.xml',
    ],
    'license': 'LGPL-3',
    'application': False,
}
