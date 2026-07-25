{
    'name': 'AIDT Văn bản — Kho tài liệu (DMS)',
    'version': '1.0',
    'category': 'Human Resources',
    'summary': 'Cầu nối aidt.document ↔ OCA DMS: kho tệp tập trung, quyền kế thừa (N-10/N-05/V-04)',
    'depends': ['aidt_org', 'dms'],
    'data': [
        'security/aidt_dms_groups.xml',
        'data/dms_storage.xml',
        'views/aidt_document_views.xml',
        'views/aidt_dms_menus.xml',
    ],
    'license': 'LGPL-3',
}
