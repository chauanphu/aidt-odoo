{
    'name': 'AIDT Biên bản cuộc họp',
    'version': '19.0.1.0.1',
    'category': 'Productivity/Discuss',
    'summary': 'Ghi âm, bóc băng và tóm tắt cuộc họp Discuss Meet',
    'depends': ['mail', 'calendar', 'aidt_calendar'],
    'data': [
        'security/aidt_meeting_rules.xml',
        'security/ir.model.access.csv',
        'data/ir_config_parameter.xml',
        'data/ir_cron.xml',
        'views/meeting_recording_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'aidt_meeting_minutes/static/src/recorder_service.js',
            'aidt_meeting_minutes/static/src/rtc_service_patch.js',
            'aidt_meeting_minutes/static/src/recording_banner.js',
            'aidt_meeting_minutes/static/src/recording_banner.xml',
            'aidt_meeting_minutes/static/src/recording_banner.scss',
            'aidt_meeting_minutes/static/src/call_patch.js',
        ],
        'web.assets_unit_tests': [
            'aidt_meeting_minutes/static/tests/**/*',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
