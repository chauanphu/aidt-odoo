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
    #
    # 19.0.1.2.0: dọn theo đợt chuyển sang xử lý theo lô ở docker/ai_worker.
    # GỠ sáu tham số của đường vLLM cũ (`asr_url`, `asr_api_key`,
    # `asr_response_format`, `asr_temperature`, `llm_url`, `llm_api_key`) —
    # chúng phục vụ models/asr_client.py và models/summary_client.py, cả hai
    # đã bị xoá. THÊM `ai_service_url` và `asr_ct2_model`.
    #
    # Hai nửa xử lý KHÁC NHAU, và nửa sau là chỗ tôi đã đoán sai một lần:
    #   * Tham số THÊM (`param_ai_service_url`, `param_asr_ct2_model`) là
    #     xml_id MỚI nên vẫn được tạo khi nâng cấp dù khối là `noupdate="1"`
    #     — cùng cơ chế đã kiểm chứng ở 19.0.1.0.3. Không cần migration.
    #   * Tham số GỠ thì PHẢI có migration. Với khối dữ liệu thường, xoá bản
    #     ghi khỏi XML là đủ vì `_process_end` tự dọn xml_id biến mất; nhưng
    #     bản ghi `noupdate="1"` được GIỮ LẠI nguyên vẹn. Kiểm chứng bằng
    #     TestConfig.test_khong_con_tham_so_cua_duong_vllm_da_go: sau `-u`,
    #     `aidt_meeting.asr_url` vẫn còn nguyên giá trị quản trị viên tự đặt.
    #     Bản dọn thật ở migrations/19.0.1.2.0/post-migration.py.
    #
    # 19.0.1.2.1: XOÁ prompt mặc định (`asr_prompt` -> rỗng). Đây là lần ĐẢO
    # HƯỚNG so với 19.0.1.1.1, không phải một lần tinh chỉnh tiếp: bản đó
    # kết luận lỗi nằm ở KIỂU VIẾT prompt (liệt kê -> văn xuôi), và kết luận
    # đó SAI. Văn xuôi chỉ làm hỏng hóc bớt lộ liễu; cơ chế vẫn nguyên —
    # Whisper coi prompt là văn bản đứng trước audio nên gặp cửa sổ nghèo
    # tín hiệu là nó ĐỌC TIẾP prompt thay vì phiên âm.
    # Đo 10/08/2026 (bản ghi 2858): có prompt -> một segment 44 giây mang
    # nguyên văn prompt, NUỐT MẤT 44 giây phát biểu thật; không prompt ->
    # đúng 44 giây đó ra 8 câu thật. Trên 2797, có/không prompt cho từ vựng
    # GIỐNG HỆT nhau. Lợi ích 0, thiệt hại mất nửa phần phát biểu của một
    # người. Cần migration vì `param_asr_prompt` là bản ghi noupdate đã tồn
    # tại — cùng cái bẫy đã cắn ba lần trước.
    #
    # 19.0.1.3.0: chủ phòng điều khiển ghi âm, thông báo bắt buộc, tạm dừng
    # và ghi tiếp. Migration ở migrations/19.0.1.3.0/pre-migration.py làm bốn
    # việc mà Odoo không tự làm: chỉ mục duy nhất MỘT PHẦN không cập nhật
    # theo mệnh đề WHERE mới (`init()` dùng IF NOT EXISTS), khoá duy nhất của
    # chunk phải gỡ trước khi thêm `take`, và hai bảng chết cần dọn.
    #
    # 19.0.1.3.1: "Quản lý cuộc họp" thôi làm ứng dụng riêng, chuyển vào làm
    # mục con của Thảo luận (giữa "Kênh" và "Cấu hình"). Không cần migration:
    # `menu_meeting_root` biến mất khỏi file dữ liệu nên Odoo tự dọn nó ở
    # bước vacuum cuối lần nâng cấp, còn `menu_meeting_recording` chỉ đổi
    # parent/name/sequence trên chính bản ghi cũ. Bump phiên bản để môi
    # trường nào nâng cấp theo số phiên bản cũng nạp lại được menu.
    #
    # 19.0.1.4.0: cuộc họp thành một loại phòng riêng — mục "Họp" trong thanh
    # bên Thảo luận, ghi âm chỉ còn trong phòng họp, trang "Quản lý cuộc họp"
    # tạo/sửa cuộc họp, trang bản ghi đổi thành "Lịch sử cuộc họp". Không cần
    # migration: bất biến "phòng họp = kênh có calendar.event" đọc từ quan hệ
    # `calendar_event_ids` upstream đã có sẵn, nên các phòng họp cũ tự động
    # được nhận đúng mà không phải sửa dữ liệu.
    'version': '19.0.1.4.0',
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
        'views/calendar_event_views.xml',
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
            'aidt_meeting_minutes/static/src/scss/meeting_dashboard.scss',
        ],
        'web.assets_unit_tests': [
            'aidt_meeting_minutes/static/tests/**/*',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
