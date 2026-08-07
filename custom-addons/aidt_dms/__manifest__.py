{
    'name': 'AIDT Văn bản — Kho tài liệu (DMS)',
    'version': '1.0',
    'category': 'Human Resources',
    'summary': 'Cầu nối aidt.document ↔ OCA DMS: kho tệp tập trung, quyền kế thừa & Trích xuất AI (OCR)',
    'depends': ['aidt_org', 'dms'],
    'data': [
        'security/aidt_dms_groups.xml',
        'security/ir.model.access.csv',
        'data/dms_storage.xml',
        'wizards/aidt_document_ocr_wizard_views.xml',
        'views/aidt_document_views.xml',
        'views/aidt_dms_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'aidt_dms/static/src/js/form_controller_dirty.js',
        ],
    },
    'license': 'LGPL-3',
}
