{
    'name': 'AIDT Biên bản cuộc họp',
    # 19.0.1.0.3: thêm tham số `aidt_meeting.asr_response_format`. KHÔNG cần
    # script migration — `noupdate="1"` chỉ bỏ qua bản ghi ĐÃ CÓ trong
    # ir_model_data, còn xml_id mới thì vẫn được TẠO khi nâng cấp (đã kiểm
    # chứng trên `aidt_demo` — một CSDL cài từ trước — ngày 05/08/2026:
    # tham số xuất hiện với giá trị `json` sau `-u aidt_meeting_minutes`).
    # Bump phiên bản để môi trường tự nâng cấp theo số phiên bản cũng nạp
    # lại file dữ liệu này.
    'version': '19.0.1.0.3',
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
