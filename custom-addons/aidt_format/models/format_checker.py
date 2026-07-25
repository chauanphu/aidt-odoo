import logging
import time

from odoo import api, models

from odoo.addons.aidt_format_engine.findings import ERROR, Finding
from odoo.addons.aidt_format_engine.parser import UnreadableDocx, parse_docx
from odoo.addons.aidt_format_engine.rules import run_rules
from odoo.addons.aidt_format_engine.zones import detect_zones

_logger = logging.getLogger(__name__)


class AidtFormatChecker(models.AbstractModel):
    _name = 'aidt.format.checker'
    _description = 'Cửa vào kiểm tra thể thức'

    @api.model
    def check(self, docx_bytes, ruleset):
        """Kiểm thể thức một file .docx theo một bộ luật.

        Trả list[dict], mỗi dict là một phát hiện. KHÔNG ghi bản ghi nào —
        việc lưu thành aidt.document.finding thuộc module nghiệp vụ, nhờ vậy
        engine không cần biết finding được lưu ở đâu.
        """
        spec = ruleset.spec()
        started = time.monotonic()
        try:
            doc = parse_docx(docx_bytes)
        except UnreadableDocx as exc:
            # Không cho traceback nổ ra: file sai định dạng là chuyện thường
            # (.doc cũ, PDF đổi tên), người dùng cần thấy lý do trên form.
            return [Finding(
                rule_id='file.unreadable', severity=ERROR, zone='',
                location='Toàn tệp',
                expected='Tệp .docx đọc được',
                actual=str(exc),
                suggestion='Mở bằng Word và lưu lại ở định dạng .docx '
                           '(không phải .doc hay PDF)').as_dict()]
        detect_zones(doc)
        findings = run_rules(doc, spec)
        # QĐ-5: engine chạy đồng bộ, nên phải đo được. Vượt ngưỡng thì tách async.
        _logger.info(
            'Kiểm thể thức %s: %d đoạn, %d phát hiện, %.0fms',
            ruleset.display_name, len(doc.paras), len(findings),
            (time.monotonic() - started) * 1000)
        return [finding.as_dict() for finding in findings]
