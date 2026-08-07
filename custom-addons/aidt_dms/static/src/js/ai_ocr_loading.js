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

    // Create and append compact active progress bar alert banner
    const alertBox = document.createElement("div");
    alertBox.className = "ai-ocr-active-progress-banner alert alert-success p-2 my-2 border border-success-subtle shadow-sm rounded-2 mx-auto w-100";
    alertBox.style.maxWidth = "90%";
    alertBox.style.fontSize = "12px";
    alertBox.innerHTML = `
        <div class="d-flex justify-content-between align-items-center mb-1">
            <span class="fw-bold text-success" style="font-size: 11px;">
                <i class="fa fa-circle-o-notch fa-spin me-1"></i>
                <span class="ai-ocr-status-text">Đang kết nối Gemma 4 AI Vision...</span>
            </span>
            <span class="badge bg-success text-white px-2 py-0 rounded-pill fw-bold ai-ocr-percent-text" style="font-size: 10px;">2%</span>
        </div>
        <div class="progress" style="height: 8px; background-color: #e9ecef; border-radius: 4px; overflow: hidden;">
            <div class="progress-bar progress-bar-striped progress-bar-animated bg-success ai-ocr-bar" role="progressbar" style="width: 2%; transition: width 0.15s linear;"></div>
        </div>
        <div class="d-flex justify-content-between text-muted mt-1" style="font-size: 10px;">
            <span>1. Đọc OCR bố cục</span>
            <span>2. Suy luận ngữ cảnh</span>
            <span>3. Tóm tắt &amp; Định tuyến</span>
        </div>
    `;

    modalBody.appendChild(alertBox);

    const bar = alertBox.querySelector(".ai-ocr-bar");
    const statusText = alertBox.querySelector(".ai-ocr-status-text");
    const percentText = alertBox.querySelector(".ai-ocr-percent-text");

    let pct = 2;
    const stages = [
        { pct: 20, text: "1. Đọc OCR bố cục & chỉ mục trang 1..." },
        { pct: 50, text: "2. Gemma 4 AI đang suy luận ngữ cảnh toàn văn..." },
        { pct: 78, text: "3. Tóm tắt Trích yếu 1 câu & thẩm định Mật/Khẩn..." },
        { pct: 95, text: "4. Hoàn tất định tuyến Đơn vị Odoo..." },
    ];

    let stageIdx = 0;
    // Calibrated timer: step 1-2% every 110ms (~4 seconds total to reach 98%)
    const interval = setInterval(() => {
        if (pct < 98) {
            // Smooth slow progression: increment 1-2% per tick
            pct += (pct < 70) ? (Math.floor(Math.random() * 2) + 2) : (Math.floor(Math.random() * 2) + 1);
            if (pct > 98) pct = 98;
            if (bar) {
                bar.style.width = pct + "%";
            }
            if (percentText) percentText.textContent = pct + "%";

            if (stageIdx < stages.length && pct >= stages[stageIdx].pct) {
                if (statusText) statusText.textContent = stages[stageIdx].text;
                stageIdx++;
            }
        } else {
            clearInterval(interval);
        }
    }, 110);
}, true);
