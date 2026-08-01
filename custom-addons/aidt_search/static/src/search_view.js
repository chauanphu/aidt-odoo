/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState } from "@odoo/owl";

const MARK_OPEN = "<mark>";
const MARK_CLOSE = "</mark>";

function escapeHtml(text) {
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

/**
 * `ts_headline()` (search_service.py) chèn <mark>/</mark> làm dấu highlight
 * TRỰC TIẾP vào nội dung tài liệu gốc — nội dung đó do người dùng khác tải
 * lên nên KHÔNG đáng tin. Nếu render thẳng chuỗi trả về bằng t-out, bất kỳ
 * HTML/script nào lỡ có trong văn bản gốc (cố ý hay không) sẽ chạy trong
 * phiên của người xem kết quả tìm kiếm — XSS lưu trữ kinh điển đi qua đúng
 * đường mà tính năng highlight cần "render như markup".
 *
 * Tách chuỗi tại đúng hai token cố định server chèn vào, escape mọi đoạn văn
 * bản NẰM GIỮA (kể cả khi nó chứa "<mark>" giả mạo do tình cờ trùng chữ),
 * chỉ giữ nguyên literal hai token đó làm thẻ thật. `String.split` với regex
 * có capture group trả về cả phần khớp lẫn phần không khớp nên không cần tự
 * ghép lại thủ công.
 */
function highlightSnippet(raw) {
    if (!raw) {
        return "";
    }
    return raw
        .split(/(<mark>|<\/mark>)/g)
        .map((part) => (part === MARK_OPEN || part === MARK_CLOSE) ? part : escapeHtml(part))
        .join("");
}

// Nhãn hiển thị cho facet: `_facets()` (search_service.py) trả `doc_type`/
// `secrecy` bằng đúng key selection ('ke_hoach', 'thuong', ...) và
// `department_id` bằng id trần (`value.id`, không phải `display_name` —
// `_read_group` trả recordset nhưng code chỉ giữ lại `.id`). Hai selection
// field còn đọc được (key selection vẫn có nghĩa với người quen nghiệp vụ),
// nhưng id phòng ban trần thì vô nghĩa với người dùng cuối ("Đơn vị: 14").
// Không sửa được ở server: `test_search_service.py` khoá CHẶT hình dạng
// 2-tuple `(value, count)` của facet qua `dict(result['facets']['doc_type'])`
// — thêm phần tử thứ ba làm `dict()` ném lỗi ngay. Giải bằng một lời gọi
// đọc tên phòng ban PHỤ, chỉ để hiển thị — không đụng gì tới domain lọc
// (vẫn dùng đúng `row[0]` là id, quyền vẫn hoàn toàn do ir.rule server-side).
const FACET_LABELS = {
    doc_type: "Loại văn bản",
    department_id: "Đơn vị",
    secrecy: "Độ mật",
};

function emptyResult() {
    return {
        query: "", reference: null, filters: [], documents: [], facets: {},
        total: 0, truncated: false, channels_used: [], degraded: false,
        warning: false, indexing: 0,
    };
}

export class AidtSearchView extends Component {
    static template = "aidt_search.SearchView";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            query: "",
            loading: false,
            searched: false,
            result: emptyResult(),
            activeFacets: {},
            departmentNames: {},
        });
    }

    facetLabel(field) {
        return FACET_LABELS[field] || field;
    }

    facetValueLabel(field, value) {
        if (field === "department_id") {
            return this.state.departmentNames[value] || value;
        }
        return value;
    }

    async loadDepartmentNames(ids) {
        if (!ids.length) {
            return;
        }
        const rows = await this.orm.call("hr.department", "read", [ids, ["name"]]);
        for (const row of rows) {
            this.state.departmentNames[row.id] = row.name;
        }
    }

    get facetDomain() {
        // Facet là bộ lọc PHỤ trên tập đã lọc quyền — không bao giờ mở rộng
        // phạm vi, chỉ thu hẹp. Quyền vẫn do ir.rule quyết ở phía server.
        const domain = [];
        for (const [field, value] of Object.entries(this.state.activeFacets)) {
            if (value !== undefined && value !== null) {
                domain.push([field, "=", value]);
            }
        }
        return domain;
    }

    highlightSnippet(raw) {
        return highlightSnippet(raw);
    }

    async search() {
        if (!this.state.query.trim()) {
            return;
        }
        this.state.loading = true;
        try {
            this.state.result = await this.orm.call(
                "aidt.search.service", "search",
                [this.state.query, this.facetDomain],
            );
            this.state.searched = true;
            const deptIds = (this.state.result.facets.department_id || []).map((row) => row[0]);
            await this.loadDepartmentNames(deptIds);
        } finally {
            this.state.loading = false;
        }
    }

    onKeydown(ev) {
        if (ev.key === "Enter") {
            this.search();
        }
    }

    removeFilter(field) {
        // Chip "Đã hiểu" xoá được: người dùng luôn thấy hệ thống đã diễn giải
        // câu hỏi thế nào và sửa được khi nó hiểu sai — nhưng xoá phải có TÁC
        // DỤNG THẬT, không chỉ giấu chip đi trong khi lượt tìm kế tiếp gửi
        // lại NGUYÊN VĂN câu hỏi cũ và `parse_query()` phía server bóc lại
        // đúng filter đó lần nữa. Dùng `span` (vị trí của cụm từ sinh ra
        // filter này trong câu hỏi gốc, do server trả kèm) để cắt ĐÚNG cụm
        // đó khỏi câu hỏi rồi tìm lại — filter biến mất vì cụm từ kích hoạt
        // nó không còn, không phải vì giao diện che nó đi.
        const target = this.state.result.filters.find((f) => f.field === field);
        if (!target) {
            return;
        }
        const base = this.state.result.query;
        const [start, end] = target.span;
        const edited = (base.slice(0, start) + " " + base.slice(end))
            .replace(/\s+/g, " ").trim();
        this.state.query = edited;
        this.search();
    }

    toggleFacet(field, value) {
        this.state.activeFacets[field] =
            this.state.activeFacets[field] === value ? undefined : value;
        this.search();
    }

    openDocument(documentId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "aidt.document",
            res_id: documentId,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

registry.category("actions").add("aidt_search.search_view", AidtSearchView);
