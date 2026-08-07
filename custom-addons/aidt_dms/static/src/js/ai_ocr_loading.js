/** @odoo-module **/

document.addEventListener("click", function (ev) {
    const btn = ev.target.closest("button[name='action_run_ai_ocr']");
    if (!btn) return;

    const modal = btn.closest(".modal-content") || document;
    const progressBox = modal.querySelector(".ai-ocr-progress-container");
    if (progressBox) {
        progressBox.style.display = "block";
        const bar = progressBox.querySelector(".ai-ocr-bar");
        const statusText = progressBox.querySelector(".ai-ocr-status-text");
        const percentText = progressBox.querySelector(".ai-ocr-percent-text");

        let pct = 0;
        const stages = [
            { pct: 20, text: "1. Đọc OCR bố cục & phân tích trang 1..." },
            { pct: 50, text: "2. Gemma 4 AI đang suy luận ngữ cảnh toàn văn..." },
            { pct: 80, text: "3. Tóm tắt Trích yếu cốt lõi & thẩm định Mật/Khẩn..." },
            { pct: 98, text: "4. Hoàn tất định tuyến Đơn vị Odoo (100%)..." },
        ];

        let stageIdx = 0;
        const interval = setInterval(() => {
            if (pct < 98) {
                pct += Math.floor(Math.random() * 6) + 5;
                if (pct > 98) pct = 98;
                if (bar) bar.style.width = pct + "%";
                if (percentText) percentText.textContent = pct + "%";

                if (stageIdx < stages.length && pct >= stages[stageIdx].pct) {
                    if (statusText) statusText.textContent = stages[stageIdx].text;
                    stageIdx++;
                }
            } else {
                clearInterval(interval);
            }
        }, 150);
    }
});
