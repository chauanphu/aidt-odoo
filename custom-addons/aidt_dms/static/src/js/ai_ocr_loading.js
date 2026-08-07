/** @odoo-module **/

// Intercept click on "Phân tích AI OCR (Xem trước)" button in capture phase
document.addEventListener("click", function (ev) {
    const btn = ev.target.closest("button[name='action_run_ai_ocr']");
    if (!btn) return;

    const modalContent = btn.closest(".modal-content");
    const modalBody = modalContent ? (modalContent.querySelector(".modal-body") || modalContent) : document.body;

    // Remove any existing banner first
    const existing = modalBody.querySelector(".ai-ocr-active-progress-banner");
    if (existing) {
        existing.remove();
    }

    // Create and append active progress bar alert banner
    const alertBox = document.createElement("div");
    alertBox.className = "ai-ocr-active-progress-banner alert alert-success p-3 my-3 border border-success-subtle shadow-sm rounded-3";
    alertBox.innerHTML = `
        <div class="d-flex justify-content-between align-items-center mb-1">
            <strong class="text-success small">
                <i class="fa fa-circle-o-notch fa-spin me-1"></i>
                <span class="ai-ocr-status-text">Đang kết nối Gemma 4 AI Vision phân tích tệp...</span>
            </strong>
            <span class="badge bg-success text-white px-2 py-1 rounded-pill small fw-bold ai-ocr-percent-text">5%</span>
        </div>
        <div class="progress" style="height: 16px; background-color: #e9ecef; border-radius: 8px; overflow: hidden;">
            <div class="progress-bar progress-bar-striped progress-bar-animated bg-success ai-ocr-bar" role="progressbar" style="width: 5%; font-size: 11px; font-weight: bold; line-height: 16px; transition: width 0.15s ease-in-out;">5%</div>
        </div>
        <div class="d-flex justify-content-between text-muted small mt-2" style="font-size: 11px;">
            <span>1. Đọc OCR bố cục trang 1</span>
            <span>2. Suy luận ngữ cảnh toàn văn</span>
            <span>3. Tóm tắt &amp; Định tuyến Odoo</span>
        </div>
    `;

    modalBody.appendChild(alertBox);

    const bar = alertBox.querySelector(".ai-ocr-bar");
    const statusText = alertBox.querySelector(".ai-ocr-status-text");
    const percentText = alertBox.querySelector(".ai-ocr-percent-text");

    let pct = 5;
    const stages = [
        { pct: 20, text: "1. Đọc OCR bố cục & chỉ mục trang 1..." },
        { pct: 50, text: "2. Gemma 4 AI đang suy luận ngữ cảnh toàn văn..." },
        { pct: 75, text: "3. Tóm tắt Trích yếu 1 câu & thẩm định Mật/Khẩn..." },
        { pct: 95, text: "4. Hoàn tất định tuyến Đơn vị Odoo..." },
    ];

    let stageIdx = 0;
    const interval = setInterval(() => {
        if (pct < 95) {
            pct += Math.floor(Math.random() * 6) + 4;
            if (pct > 95) pct = 95;
            if (bar) {
                bar.style.width = pct + "%";
                bar.textContent = pct + "%";
            }
            if (percentText) percentText.textContent = pct + "%";

            if (stageIdx < stages.length && pct >= stages[stageIdx].pct) {
                if (statusText) statusText.textContent = stages[stageIdx].text;
                stageIdx++;
            }
        } else {
            clearInterval(interval);
        }
    }, 150);
}, true);
