{
    'name': 'AIDT Biên bản cuộc họp',
    'version': '19.0.1.0.0',
    'category': 'Productivity/Discuss',
    'summary': 'Ghi âm, bóc băng và tóm tắt cuộc họp Discuss Meet',
    'depends': ['mail', 'calendar', 'aidt_calendar'],
    'data': [
        'security/aidt_meeting_rules.xml',
        'security/ir.model.access.csv',
        'data/ir_config_parameter.xml',
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
