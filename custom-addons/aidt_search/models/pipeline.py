from odoo import models


class AidtIndexPipeline(models.AbstractModel):
    """Chỗ giữ tên cho pipeline trích xuất → chunk → embed → ghi.

    Task 13 chỉ cần model này TỒN TẠI để `_cron_process` gọi được và để
    `TestDedup` patch được `run` trước khi job thật sự chạy pipeline — thân
    hàm do Task 14 viết.
    """
    _name = 'aidt.index.pipeline'
    _description = 'Pipeline chỉ mục tài liệu (khung, Task 14 điền thân)'

    def run(self, job):
        raise NotImplementedError
