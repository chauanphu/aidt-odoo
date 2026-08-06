# Ảnh cho aidt-asr (docker-compose.ai.yml). Ảnh gốc vllm/vllm-openai KHÔNG
# kèm bộ giải mã audio (`soundfile`/`av`) — thiếu chúng thì MỌI request tới
# /v1/audio/transcriptions đều 400 "Invalid or unsupported audio file", bất
# kể multipart body đúng hay sai (xác nhận thật bằng cách trace import lỗi
# trong container ngày 05/08/2026, xem báo cáo Task 11).
#
# Cài ở bước build, KHÔNG ở bước chạy (không dùng `command: bash -c "pip
# install ... && vllm serve ..."`):
#   - build một lần, không tải lại PyPI mỗi khi container được tạo lại;
#   - không phụ thuộc mạng lúc khởi động — chạy được trên host air-gapped;
#   - không thêm một điểm hỏng (PyPI sập, rate limit) vào MỌI lần restart;
#   - không cộng dồn thời gian cài đặt vào ngân sách retry của healthcheck.
#
# Ghim cả tag ảnh gốc lẫn version hai gói — build lại sau này phải cho đúng
# một kết quả, không trôi theo `latest`.
FROM vllm/vllm-openai:v0.26.0

RUN pip install --no-cache-dir soundfile==0.14.0 av==18.0.0
