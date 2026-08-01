{
    'name': 'AIDT Tìm kiếm thông minh',
    'version': '1.0',
    'category': 'Document Management',
    'summary': 'Chỉ mục lai (vector + lexical) và tìm kiếm ngữ nghĩa trên kho văn bản '
               '(V-10 → V-14, S-11, N-12)',
    # `aidt_vanban_den` thêm vào để gắn menu "Tìm kiếm thông minh" và badge
    # chỉ mục lên đúng màn hình "Văn bản đến" đang hoạt động (menu/form của
    # aidt_org bị vô hiệu hoá — active="0"). Không có cạnh ngược lại:
    # aidt_vanban_den không phụ thuộc aidt_search, nên không có chu trình.
    'depends': ['aidt_dms', 'aidt_org', 'aidt_vanban_den'],
    'data': [
        'security/ir.model.access.csv',
        'security/aidt_search_rules.xml',
        'data/ir_config_parameter.xml',
        'data/ir_cron.xml',
        'views/index_job_views.xml',
        'views/aidt_document_views.xml',
        'views/search_actions.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'aidt_search/static/src/search_view.js',
            'aidt_search/static/src/search_view.xml',
            'aidt_search/static/src/search_view.scss',
        ],
    },
    'license': 'LGPL-3',
    'application': False,
}
