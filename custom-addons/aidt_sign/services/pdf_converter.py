import tempfile
import subprocess
import os
import logging

_logger = logging.getLogger(__name__)

def convert_to_pdf(file_content: bytes, filename: str) -> bytes:
    """
    Chuyển đổi file dự thảo (.docx/.doc) sang chuẩn file PDF bằng LibreOffice Headless CLI.
    Nếu file truyền vào đã là PDF thì trả về chính file đó.
    """
    if not file_content:
        raise ValueError("Nội dung file rỗng.")

    filename_lower = filename.lower()
    if filename_lower.endswith('.pdf') or file_content.startswith(b'%PDF'):
        return file_content

    with tempfile.TemporaryDirectory() as tmp_dir:
        input_path = os.path.join(tmp_dir, filename)
        with open(input_path, 'wb') as f:
            f.write(file_content)

        cmd = [
            'soffice', '--headless', '--convert-to', 'pdf',
            '--outdir', tmp_dir, input_path
        ]
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
            if res.returncode != 0:
                _logger.error("LibreOffice conversion failed: %s", res.stderr.decode('utf-8', errors='ignore'))
                raise RuntimeError(f"Chuyển đổi PDF thất bại: {res.stderr.decode('utf-8', errors='ignore')}")
        except Exception as e:
            _logger.error("Error executing LibreOffice: %s", str(e))
            raise RuntimeError(f"Lỗi hệ thống khi chuyển đổi file Word sang PDF: {str(e)}")

        base_name = os.path.splitext(filename)[0]
        output_pdf_path = os.path.join(tmp_dir, f"{base_name}.pdf")
        if not os.path.exists(output_pdf_path):
            # Fallback search any .pdf in tmp_dir
            pdf_files = [f for f in os.listdir(tmp_dir) if f.endswith('.pdf')]
            if pdf_files:
                output_pdf_path = os.path.join(tmp_dir, pdf_files[0])
            else:
                raise FileNotFoundError(f"Không tìm thấy file PDF xuất ra sau khi convert từ {filename}")

        with open(output_pdf_path, 'rb') as f:
            return f.read()
