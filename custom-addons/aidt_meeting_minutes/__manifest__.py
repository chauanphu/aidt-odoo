{
    'name': 'AIDT Biên bản cuộc họp',
    # 19.0.1.0.3: thêm tham số `aidt_meeting.asr_response_format`. KHÔNG cần
    # script migration — `noupdate="1"` chỉ bỏ qua bản ghi ĐÃ CÓ trong
    # ir_model_data, còn xml_id mới thì vẫn được TẠO khi nâng cấp (đã kiểm
    # chứng trên `aidt_demo` — một CSDL cài từ trước — ngày 05/08/2026:
    # tham số xuất hiện với giá trị `json` sau `-u aidt_meeting_minutes`).
    # Bump phiên bản để môi trường tự nâng cấp theo số phiên bản cũng nạp
    # lại file dữ liệu này.
    #
    # 19.0.1.1.0: chất lượng bóc băng — ba tham số giải mã mới cộng đổi model
    # mặc định. Hai nửa này xử lý KHÁC NHAU, và lý do khác nhau là điều dễ
    # làm sai nhất ở đây:
    #
    #   * `asr_language`, `asr_prompt`, `asr_temperature` — xml_id MỚI, nên
    #     chúng được TẠO khi nâng cấp đúng như `asr_response_format` ở
    #     19.0.1.0.3. KHÔNG cần migration.
    #   * `asr_model` (vinai/PhoWhisper-large -> openai/whisper-large-v3) —
    #     xml_id `param_asr_model` ĐÃ TỒN TẠI trên mọi CSDL cài từ trước, và
    #     `noupdate="1"` nghĩa là bản ghi đã có thì KHÔNG được ghi đè. Sửa
    #     giá trị trong XML sẽ không bao giờ tới `aidt_demo`: mọi lần bóc
    #     băng vẫn âm thầm dùng model cũ trong khi file dữ liệu nói đã đổi.
    #     PHẢI có migrations/19.0.1.1.0/post-migration.py — và nó chỉ đổi khi
    #     giá trị hiện tại đúng bằng mặc định cũ, để không đè lên quản trị
    #     viên đã tự trỏ sang dịch vụ khác. Cùng cái bẫy đã cắn `llm_url`/
    #     `llm_model` ở 19.0.1.0.1.
    #
    # Bump lên nhánh .1.x (không phải .0.4) vì đây là đổi hành vi mặc định
    # kèm migration, không phải vá thêm một tham số.
    #
    # 19.0.1.1.1: prompt mặc định đổi từ kiểu LIỆT KÊ sang VĂN XUÔI. Bản
    # liệt kê gây sự cố thật ngay trong ngày ra mắt (bản ghi 1141: model
    # nhả ngược prompt rồi lặp 18 lần giữa biên bản một cuộc họp thật).
    # `param_asr_prompt` đã tồn tại từ 19.0.1.1.0 nên `noupdate="1"` sẽ
    # KHÔNG cập nhật nó — phải có migrations/19.0.1.1.1/post-migration.py,
    # cùng lý do với `asr_model` ở bản trước.
    'version': '19.0.1.1.1',
    'category': 'Productivity/Discuss',
    'summary': 'Ghi âm, bóc băng và tóm tắt cuộc họp Discuss Meet',
    'depends': ['mail', 'calendar', 'aidt_calendar'],
    # `av` (PyAV) + `numpy`: models/audio_prep.py giải mã MP3, đo năng lượng
    # theo khung và đóng gói WAV trước khi gọi ASR. Khai báo ở đây để Odoo
    # CHẶN việc cài module khi thiếu gói, kèm thông báo nói rõ thiếu gì.
    #
    # Không thừa dù Dockerfile đã cài: Dockerfile chỉ mô tả ẢNH của dự án
    # này, còn manifest theo module đi bất cứ đâu nó được cài. Ngày
    # 05/08/2026 cả hai gói đều CHỈ có ở lớp ghi của container đang chạy chứ
    # không có trong ảnh — thiếu dòng này thì triệu chứng là `models/__init__`
    # ném ModuleNotFoundError giữa lúc nạp registry, một lỗi không nói được
    # cho ai biết nguyên nhân là gì.
    'external_dependencies': {'python': ['av', 'numpy']},
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
            'aidt_meeting_minutes/static/src/recording_subtitle.js',
            'aidt_meeting_minutes/static/src/recording_subtitle.xml',
            'aidt_meeting_minutes/static/src/recording_subtitle.scss',
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
