# Odoo AI Meeting Summary

## 1. Tổng quan

Feature này được phát triển thành một Addon / App độc lập (Quản lý cuộc họp) trên hệ sinh thái Odoo (tương tác với Discuss / Calendar) nhằm:
- Ghi âm hoặc nhận file audio của cuộc họp.
- Chuyển giọng nói thành văn bản bằng Whisper hoặc PhoWhisper.
- Tóm tắt nội dung bằng Ollama chạy Gemma 3 12B.
- Trích xuất ý chính, quyết định, công việc cần làm và thời hạn.
- Sinh biên bản cuộc họp.
- Lưu transcript và summary trong Odoo.
- Hiển thị, chỉnh sửa, xác nhận và chia sẻ kết quả trong Discuss / Meeting.

---

## 2. Actor

| Actor | Vai trò |
|---|---|
| Người tổ chức cuộc họp | Tạo meeting, ghi âm, yêu cầu AI xử lý, xác nhận và chia sẻ kết quả |
| Người tham gia | Xem transcript, summary, action items và phản hồi |
| Quản trị viên hệ thống | Cấu hình AI model, prompt, phân quyền và theo dõi lỗi |
| Whisper / PhoWhisper | Chuyển audio thành transcript |
| Ollama Gemma 3 12B | Tóm tắt transcript và trích xuất dữ liệu có cấu trúc |
| Odoo Background Worker | Xử lý các job AI bất đồng bộ |

---

# 3. Use Case Diagram dạng ký tự

```text
ACTOR NGƯỜI DÙNG                                      DỊCH VỤ BÊN NGOÀI
────────────────                                      ─────────────────
[Người tổ chức]                                       [Whisper/PhoWhisper]
[Người tham gia]                                      [Ollama Gemma 3 12B]
[Quản trị viên]


+====================================================================================+
|                     ODOO DISCUSS / MEETING + AI SUMMARY MODULE                     |
|                                                                                    |
|  [Người tổ chức cuộc họp]                                                          |
|          |                                                                         |
|          +--------> (UC01. Tạo / lên lịch cuộc họp)                                |
|          |                                                                         |
|          +--------> (UC02. Bắt đầu / kết thúc cuộc họp)                            |
|          |                                                                         |
|          +--------> (UC03. Bắt đầu / dừng ghi âm)                                  |
|          |                          |                                              |
|          |                          +----------<<include>>----------+               |
|          |                                                           |               |
|          +--------> (UC04. Upload file audio / video)                |               |
|                              |                                      |               |
|                              +----------<<include>>----------+       |               |
|                                                             |       |               |
|                                                             v       v               |
|                                                    (UC05. Lưu file meeting)         |
|                                                             |                      |
|                                                             v                      |
|                                                    (UC06. Tạo AI processing job)   |
|                                                             |                      |
|                                                             v                      |
|                                                    (UC07. Tiền xử lý audio)         |
|                                                             |                      |
|                                                             v                      |
|                                                    (UC08. Speech-to-Text)           |
|                                                             |                      |
|                                                             v                      |
|                                                    (UC09. Lưu transcript)           |
|                                                             |                      |
|                                                             v                      |
|                                                    (UC10. Tóm tắt meeting)          |
|                                                       /       |       \             |
|                                                      v        v        v            |
|                                           (UC11. Ý chính)     |   (UC13. Quyết định)|
|                                                            |                      |
|                                                            v                      |
|                                                 (UC12. Action items)                |
|                                                            |                      |
|                                                            v                      |
|                                                 (UC14. Tạo biên bản họp)            |
|                                                                                    |
|  [Người tổ chức cuộc họp]                                                          |
|          |                                                                         |
|          +--------> (UC15. Xem transcript và summary)                              |
|          |                                                                         |
|          +--------> (UC16. Chỉnh sửa transcript / summary)                         |
|          |                                                                         |
|          +--------> (UC17. Xác nhận / phê duyệt kết quả AI)                        |
|          |                                                                         |
|          +--------> (UC18. Regenerate summary)                                     |
|          |                                                                         |
|          +--------> (UC19. Chia sẻ summary cho người tham gia)                     |
|          |                                                                         |
|          +--------> (UC20. Tạo task từ action items)                               |
|                                                                                    |
|  [Người tham gia]                                                                  |
|          |                                                                         |
|          +--------> (UC21. Xem summary trong Discuss / Meeting)                    |
|          |                                                                         |
|          +--------> (UC22. Xem transcript theo timestamp)                          |
|          |                                                                         |
|          +--------> (UC23. Tìm kiếm transcript / summary)                          |
|          |                                                                         |
|          +--------> (UC24. Bình luận / phản hồi kết quả)                           |
|                                                                                    |
|  [Quản trị viên hệ thống]                                                          |
|          |                                                                         |
|          +--------> (UC25. Cấu hình Whisper / PhoWhisper)                          |
|          |                                                                         |
|          +--------> (UC26. Cấu hình Ollama / Gemma 3 12B)                          |
|          |                                                                         |
|          +--------> (UC27. Cấu hình prompt / output schema)                        |
|          |                                                                         |
|          +--------> (UC28. Cấu hình quyền truy cập)                                |
|          |                                                                         |
|          +--------> (UC29. Xem trạng thái job / log lỗi)                           |
|          |                                                                         |
|          +--------> (UC30. Retry / hủy processing job)                             |
|                                                                                    |
+====================================================================================+


TÍCH HỢP DỊCH VỤ AI
───────────────────

(UC08. Speech-to-Text)
          |
          +-------------------------------------------> [Whisper / PhoWhisper]


(UC10. Tóm tắt meeting)
(UC11. Trích xuất ý chính)
(UC12. Trích xuất action items)
(UC13. Trích xuất quyết định)
(UC14. Tạo biên bản họp)
          |
          +-------------------------------------------> [Ollama Gemma 3 12B]
```

---

## 4. Quan hệ giữa các Use Case

```text
UC03. Ghi âm cuộc họp
   └── <<include>> UC05. Lưu file meeting

UC04. Upload audio / video
   └── <<include>> UC05. Lưu file meeting

UC05. Lưu file meeting
   └── <<include>> UC06. Tạo AI processing job

UC06. Tạo AI processing job
   └── <<include>> UC07. Tiền xử lý audio

UC07. Tiền xử lý audio
   └── <<include>> UC08. Speech-to-Text

UC08. Speech-to-Text
   └── <<include>> UC09. Lưu transcript

UC10. Tóm tắt meeting
   ├── <<include>> UC11. Trích xuất ý chính
   ├── <<include>> UC12. Trích xuất action items
   └── <<include>> UC13. Trích xuất quyết định

UC14. Tạo biên bản họp
   ├── sử dụng kết quả UC10
   ├── sử dụng kết quả UC11
   ├── sử dụng kết quả UC12
   └── sử dụng kết quả UC13

UC16. Chỉnh sửa transcript / summary
   └── <<extend>> UC15. Xem transcript và summary

UC17. Xác nhận kết quả AI
   └── <<extend>> UC16. Chỉnh sửa transcript / summary

UC18. Regenerate summary
   └── <<extend>> UC15. Xem transcript và summary

UC19. Chia sẻ summary
   └── yêu cầu UC17 đã được xác nhận

UC20. Tạo task từ action items
   └── sử dụng dữ liệu từ UC12
```

---

# 5. Flow Pipeline tổng quát

```text
+----------------------------+
| 1. TẠO / THAM GIA MEETING  |
|                            |
| - Odoo Discuss Call        |
| - Calendar Meeting         |
| - Custom Meeting Model     |
+-------------+--------------+
              |
              v
+----------------------------+
| 2. THU THẬP AUDIO          |
|                            |
| - Ghi âm trực tiếp         |
| - Upload audio             |
| - Upload video             |
+-------------+--------------+
              |
              v
+----------------------------+
| 3. LƯU FILE TRONG ODOO     |
|                            |
| - ir.attachment            |
| - meeting_id               |
| - MIME type                |
| - File size                |
| - Access permission        |
+-------------+--------------+
              |
              v
+----------------------------+
| 4. TẠO PROCESSING JOB      |
|                            |
| Status: QUEUED             |
|                            |
| - meeting_id               |
| - attachment_id            |
| - requester_id             |
| - language                 |
| - stt_model                |
| - llm_model                |
+-------------+--------------+
              |
              v
+----------------------------+
| 5. BACKGROUND WORKER       |
|                            |
| QUEUED                     |
|    -> PROCESSING_AUDIO     |
|                            |
| Có thể dùng:               |
| - OCA queue_job            |
| - Celery + Redis           |
| - Odoo cron                |
+-------------+--------------+
              |
              v
+----------------------------+
| 6. TIỀN XỬ LÝ AUDIO        |
|                            |
| - Convert WAV              |
| - Mono channel             |
| - Sample rate 16 kHz       |
| - Normalize volume         |
| - Remove silence           |
| - Split audio chunk        |
+-------------+--------------+
              |
              v
       +--------------+
       | Audio hợp lệ?|
       +------+-------+
              |
        +-----+-----+
        |           |
       NO          YES
        |           |
        v           v
+---------------+   +----------------------------+
| JOB FAILED    |   | 7. SPEECH-TO-TEXT          |
|               |   |                            |
| - Save error  |   | Whisper / PhoWhisper       |
| - Notify user |   |                            |
| - Allow retry |   | Audio chunk -> Transcript  |
+---------------+   +-------------+--------------+
                                  |
                                  v
                    +----------------------------+
                    | 8. KẾT QUẢ STT             |
                    |                            |
                    | - text                     |
                    | - start timestamp          |
                    | - end timestamp            |
                    | - confidence score         |
                    | - speaker_id nếu có        |
                    +-------------+--------------+
                                  |
                                  v
                    +----------------------------+
                    | 9. MERGE TRANSCRIPT        |
                    |                            |
                    | - Sort timestamp           |
                    | - Merge audio chunks       |
                    | - Remove duplication       |
                    | - Restore punctuation      |
                    | - Normalize Vietnamese     |
                    +-------------+--------------+
                                  |
                                  v
                    +----------------------------+
                    | 10. LƯU TRANSCRIPT         |
                    |                            |
                    | Status: TRANSCRIBED        |
                    |                            |
                    | - transcript_raw           |
                    | - transcript_clean         |
                    | - transcript_segments      |
                    +-------------+--------------+
                                  |
                                  v
                    +----------------------------+
                    | Transcript quá dài?        |
                    +-------------+--------------+
                                  |
                         +--------+--------+
                         |                 |
                        NO                YES
                         |                 |
                         |                 v
                         |   +----------------------------+
                         |   | 11. CHUNK TRANSCRIPT       |
                         |   |                            |
                         |   | - Theo token               |
                         |   | - Theo chủ đề              |
                         |   | - Theo timestamp           |
                         |   | - Có overlap               |
                         |   +-------------+--------------+
                         |                 |
                         |                 v
                         |   +----------------------------+
                         |   | Tóm tắt từng chunk         |
                         |   +-------------+--------------+
                         |                 |
                         |                 v
                         |   +----------------------------+
                         |   | Merge partial summaries    |
                         |   +-------------+--------------+
                         |                 |
                         +--------+--------+
                                  |
                                  v
                    +----------------------------+
                    | 12. PROMPT BUILDER         |
                    |                            |
                    | Context:                   |
                    | - Meeting metadata         |
                    | - Agenda                   |
                    | - Participant list         |
                    | - Transcript               |
                    | - Summary template         |
                    | - JSON output schema       |
                    +-------------+--------------+
                                  |
                                  v
                    +----------------------------+
                    | 13. OLLAMA API             |
                    |                            |
                    | Model: Gemma 3 12B         |
                    |                            |
                    | Prompt + Transcript        |
                    |          -> LLM            |
                    +-------------+--------------+
                                  |
                                  v
                    +----------------------------+
                    | 14. KẾT QUẢ AI JSON        |
                    |                            |
                    | - overview                 |
                    | - key_points[]             |
                    | - decisions[]              |
                    | - action_items[]           |
                    | - risks[]                  |
                    | - meeting_minutes          |
                    +-------------+--------------+
                                  |
                                  v
                    +----------------------------+
                    | 15. VALIDATE OUTPUT        |
                    |                            |
                    | - Parse JSON               |
                    | - Validate schema          |
                    | - Validate timestamp       |
                    | - Validate owner           |
                    | - Remove hallucination     |
                    | - Fallback / retry         |
                    +-------------+--------------+
                                  |
                                  v
                         +-----------------+
                         | Output hợp lệ?  |
                         +--------+--------+
                                  |
                           +------+------+
                           |             |
                          NO            YES
                           |             |
                           v             v
                +----------------+   +----------------------------+
                | RETRY / FAILED |   | 16. LƯU KẾT QUẢ VÀO ODOO  |
                |                |   |                            |
                | - Retry prompt |   | - meeting.summary         |
                | - Retry model  |   | - meeting.action.item     |
                | - Save error   |   | - meeting.decision        |
                +----------------+   | - ir.attachment            |
                                     | - mail.message / chatter   |
                                     +-------------+--------------+
                                                   |
                                                   v
                                     +----------------------------+
                                     | 17. HIỂN THỊ TRÊN UI       |
                                     |                            |
                                     | Discuss / Meeting tabs:    |
                                     | - Overview                 |
                                     | - Transcript               |
                                     | - Key points               |
                                     | - Decisions                |
                                     | - Action items             |
                                     | - Meeting minutes          |
                                     +-------------+--------------+
                                                   |
                                                   v
                                     +----------------------------+
                                     | 18. HUMAN REVIEW           |
                                     |                            |
                                     | - Edit transcript          |
                                     | - Edit summary             |
                                     | - Assign owner             |
                                     | - Set deadline             |
                                     | - Confirm result           |
                                     +-------------+--------------+
                                                   |
                                                   v
                                     +----------------------------+
                                     | 19. PUBLISH / SHARE        |
                                     |                            |
                                     | - Post to chatter          |
                                     | - Notify participants      |
                                     | - Export PDF / DOCX        |
                                     | - Create Odoo tasks        |
                                     +-------------+--------------+
                                                   |
                                                   v
                                     +----------------------------+
                                     | 20. COMPLETED              |
                                     |                            |
                                     | Status: DONE               |
                                     +----------------------------+
```

---

# 6. Flow trạng thái của AI Processing Job

```text
+--------+
| QUEUED |
+---+----+
    |
    v
+------------------+
| PROCESSING_AUDIO |
+--------+---------+
         |
         v
+--------------+
| TRANSCRIBING |
+------+-------+
       |
       v
+-------------+
| TRANSCRIBED |
+------+------+
       |
       v
+-------------+
| SUMMARIZING |
+------+------+
       |
       v
+------------+
| VALIDATING |
+------+-----+
       |
       v
+---------------+
| WAITING_REVIEW|
+-------+-------+
        |
        v
+-----------+
| CONFIRMED |
+-----+-----+
      |
      v
+------+
| DONE |
+------+


Bất kỳ bước nào lỗi:

PROCESSING_AUDIO
TRANSCRIBING
SUMMARIZING
VALIDATING
        |
        v
+--------+
| FAILED |
+---+----+
    |
    +------> RETRY ------> quay lại bước bị lỗi
```

---

# 7. Flow chi tiết giữa Odoo, STT và LLM

```text
Người dùng
    |
    | Upload audio / kết thúc ghi âm
    v
Odoo Discuss / Meeting UI
    |
    | POST /meeting/<id>/ai-summary
    v
Odoo Meeting Controller
    |
    | Tạo ir.attachment
    | Tạo ai.meeting.job
    v
Job Queue
    |
    | Worker lấy job
    v
Audio Processing Service
    |
    | Chuẩn hóa audio
    | Chia audio chunks
    v
Whisper / PhoWhisper
    |
    | Transcript segments
    v
Transcript Service
    |
    | Merge + normalize
    | Lưu transcript
    v
Prompt Builder
    |
    | Transcript
    | Meeting metadata
    | Agenda
    | Output JSON schema
    v
Ollama API
    |
    | Gemma 3 12B
    v
Summary Validator
    |
    | Parse JSON
    | Validate schema
    | Retry nếu lỗi
    v
Odoo Summary Service
    |
    | Lưu summary
    | Lưu decisions
    | Lưu action items
    | Sinh meeting minutes
    v
Odoo Discuss / Meeting UI
    |
    | Hiển thị kết quả
    v
Người tổ chức
    |
    | Edit / Confirm / Regenerate
    v
Publish to Chatter / Notify Participants / Create Tasks
```

---

# 8. Flow xử lý transcript dài

```text
Transcript đầy đủ
       |
       v
Đếm số token
       |
       v
+-----------------------------+
| Có vượt context window?     |
+--------------+--------------+
               |
        +------+------+
        |             |
       NO            YES
        |             |
        |             v
        |     Chia transcript thành chunks
        |             |
        |             v
        |     +-----------------------+
        |     | Chunk 1 -> Summary 1  |
        |     | Chunk 2 -> Summary 2  |
        |     | Chunk 3 -> Summary 3  |
        |     | ...                   |
        |     +-----------+-----------+
        |                 |
        |                 v
        |      Merge partial summaries
        |                 |
        |                 v
        |      Final summarization prompt
        |                 |
        +--------+--------+
                 |
                 v
        Summary cuối cùng
```

---

# 9. Flow Human-in-the-loop

```text
AI sinh kết quả
       |
       v
Status = WAITING_REVIEW
       |
       v
Người tổ chức xem kết quả
       |
       +-------------------------------+
       |                               |
       v                               v
Kết quả đúng                      Kết quả chưa đúng
       |                               |
       v                               v
Confirm                    Edit transcript / summary
       |                               |
       |                               v
       |                         Save manual changes
       |                               |
       |                               v
       |                         Confirm kết quả
       |                               |
       +---------------+---------------+
                       |
                       v
              Status = CONFIRMED
                       |
                       v
          Publish / Share / Create Tasks
```

---

# 10. Output schema đề xuất từ Gemma 3 12B

```json
{
  "title": "Tên cuộc họp",
  "overview": "Tóm tắt tổng quan của cuộc họp",
  "key_points": [
    {
      "content": "Ý chính",
      "timestamp": "00:05:30"
    }
  ],
  "decisions": [
    {
      "content": "Quyết định đã được thống nhất",
      "timestamp": "00:20:15"
    }
  ],
  "action_items": [
    {
      "task": "Công việc cần thực hiện",
      "owner": "Tên người phụ trách",
      "deadline": "2026-08-15",
      "priority": "high",
      "timestamp": "00:25:10"
    }
  ],
  "risks": [
    {
      "content": "Rủi ro hoặc vấn đề chưa xử lý"
    }
  ],
  "meeting_minutes": "Nội dung biên bản cuộc họp hoàn chỉnh"
}
```

---

# 11. Các module kỹ thuật đề xuất

```text
odoo_ai_meeting_summary/
|
+-- __init__.py
+-- __manifest__.py
|
+-- models/
|   +-- ai_meeting_job.py
|   +-- meeting_summary.py
|   +-- meeting_transcript.py
|   +-- meeting_action_item.py
|   +-- meeting_decision.py
|   +-- discuss_channel.py
|
+-- controllers/
|   +-- meeting_ai_controller.py
|
+-- services/
|   +-- audio_service.py
|   +-- stt_service.py
|   +-- transcript_service.py
|   +-- prompt_builder.py
|   +-- ollama_service.py
|   +-- summary_validator.py
|   +-- notification_service.py
|
+-- jobs/
|   +-- meeting_summary_job.py
|
+-- views/
|   +-- meeting_summary_views.xml
|   +-- meeting_transcript_views.xml
|   +-- discuss_templates.xml
|   +-- res_config_settings_views.xml
|
+-- security/
|   +-- ir.model.access.csv
|   +-- meeting_summary_security.xml
|
+-- data/
|   +-- ir_cron.xml
|   +-- default_prompt.xml
|
+-- static/src/
    +-- components/
    |   +-- meeting_ai_panel/
    |   +-- transcript_viewer/
    |   +-- action_item_list/
    |
    +-- services/
        +-- meeting_recorder.js
```

---

# 12. Pipeline rút gọn

```text
Meeting
   |
   v
Record / Upload Audio
   |
   v
Save ir.attachment
   |
   v
Create Async Job
   |
   v
Preprocess Audio
   |
   v
Whisper / PhoWhisper
   |
   v
Transcript
   |
   v
Chunk nếu quá dài
   |
   v
Prompt Builder
   |
   v
Ollama Gemma 3 12B
   |
   v
Validate JSON
   |
   v
Summary + Decisions + Action Items + Minutes
   |
   v
Save vào Odoo
   |
   v
Human Review
   |
   v
Publish / Share / Create Tasks
```
