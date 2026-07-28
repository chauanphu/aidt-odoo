{
    'name': 'AIDT Calendar - Lịch họp & Công tác Cấp ủy',
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Quản lý lịch họp, phòng họp, liên kết văn bản và bóc tách nhiệm vụ',
    'depends': ['calendar', 'resource', 'project', 'aidt_org', 'aidt_dms', 'mail', 'website'],
    'data': [
        'security/ir.model.access.csv',
        'security/aidt_calendar_rules.xml',
        'views/calendar_event_views.xml',
        'views/appointment_registration_views.xml',
        'demo/aidt_calendar_demo.xml',
    ],
    'demo': [
        'demo/aidt_calendar_demo.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
