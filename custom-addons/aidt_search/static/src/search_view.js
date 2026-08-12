/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { Component, onWillStart, useState } from "@odoo/owl";

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
        warning: false, indexing: 0, log_id: false,
    };
}

export class AidtSearchView extends Component {
    static template = "aidt_search.SearchView";
    // Client action LUÔN được `ControllerComponent` truyền cho một bộ props
    // chuẩn (`action`, `actionId`, `className`, `updateActionState`, và tuỳ
    // tình huống thêm `globalState`, `state`, `resId`). Khai `{}` nghĩa là
    // "component này không nhận prop nào" — Owl kiểm props và ném
    // `Invalid props ... unknown key 'action'` ngay lúc dựng, làm trắng cả
    // trang Văn bản.
    //
    // Lỗi này chỉ lộ ra khi BẬT CHẾ ĐỘ NHÀ PHÁT TRIỂN: Owl chỉ kiểm props ở
    // chế độ dev, nên ở chế độ thường trang vẫn chạy và không ai biết khai
    // báo đang sai.
    //
    // Dùng `standardActionServiceProps` của upstream chứ không tự liệt kê bốn
    // khoá trong thông báo lỗi: bộ đó có bảy khoá, ba khoá còn lại chỉ được
    // truyền trong tình huống khác (khôi phục trạng thái, mở kèm resId) nên
    // liệt kê tay sẽ vỡ lại đúng kiểu này ở lần sau.
    static props = { ...standardActionServiceProps };

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
            errorMessage: "",
        });
        // Nhãn cho hai facet Selection ('ke_hoach', 'thuong', ...) — cùng lý
        // do với `departmentNames`: `_facets()` trả đúng key lưu trong CSDL,
        // không phải nhãn hiển thị. Đọc MỘT LẦN lúc mount (selection field
        // không đổi giữa các lượt tìm) qua `fields_get`, một introspection
        // call chỉ-đọc, không liên quan gì tới domain lọc/quyền.
        this.selectionLabels = { doc_type: {}, secrecy: {} };
        onWillStart(async () => {
            const fields = await this.orm.call(
                "aidt.document", "fields_get",
                [["doc_type", "secrecy"], ["selection"]],
            );
            for (const name of Object.keys(this.selectionLabels)) {
                for (const [key, label] of fields[name]?.selection || []) {
                    this.selectionLabels[name][key] = label;
                }
            }
        });
    }

    facetLabel(field) {
        return FACET_LABELS[field] || field;
    }

    facetValueLabel(field, value) {
        if (field === "department_id") {
            return this.state.departmentNames[value] || value;
        }
        return this.selectionLabels[field]?.[value] || value;
    }

    async loadDepartmentNames(ids) {
        if (!ids.length) {
            return;
        }
        // Chỉ để hiển thị nhãn (xem `FACET_LABELS`/`facetValueLabel` ở
        // trên) — không phải một phần bắt buộc của kết quả tìm kiếm. Tự bọc
        // try/catch riêng, KHÔNG để lỗi ở đây (mạng chập chờn, quyền đọc
        // hr.department bị thu hẹp...) làm hỏng một lượt tìm kiếm đã thành
        // công; `facetValueLabel` đã có sẵn đường lùi về hiển thị id trần
        // khi không tra được tên, nên việc này an toàn để bỏ qua.
        try {
            const rows = await this.orm.call("hr.department", "read", [ids, ["name"]]);
            for (const row of rows) {
                this.state.departmentNames[row.id] = row.name;
            }
        } catch (err) {
            console.error("Không tải được tên đơn vị cho facet:", err);
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
        this.state.errorMessage = "";
        try {
            this.state.result = await this.orm.call(
                "aidt.search.service", "search",
                [this.state.query, this.facetDomain],
            );
            this.state.searched = true;
            const deptIds = (this.state.result.facets.department_id || []).map((row) => row[0]);
            await this.loadDepartmentNames(deptIds);
        } catch (err) {
            // Toàn bộ thiết kế tính năng này là "giảm cấp có thông báo"
            // (§5.6: embed chết vẫn tìm được, có banner). Không có nhánh
            // catch ở đây thì trường hợp NGƯỢC LẠI — lỗi mạng, AccessError
            // bất ngờ, RPC hỏng — rơi thẳng vào hộp thoại lỗi kỹ thuật
            // chung của Odoo, phá vỡ đúng nguyên tắc "luôn cho người dùng
            // biết chuyện gì đang xảy ra" mà các banner degraded/indexing
            // đã theo. `state.searched` CỐ Ý không bật ở đây: kết quả cũ
            // (nếu có) vẫn hiển thị nguyên trạng phía dưới, banner lỗi chỉ
            // báo rằng LƯỢT TÌM VỪA RỒI không thực hiện được.
            console.error("Tìm kiếm thất bại:", err);
            this.state.errorMessage =
                "Không thực hiện được tìm kiếm lúc này. Vui lòng thử lại.";
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

    async openDocument(documentId) {
        // Ghi nhận N-08 ("đã mở văn bản nào từ lượt tìm nào") — PHỤ, không
        // bao giờ được chặn việc mở văn bản. `log_id` vắng (`false`) khi
        // `_log_search()` không ghi được gì cho lượt tìm này (sudo bị chặn,
        // lỗi CSDL tạm thời...); action_click() tự kiểm tra chủ sở hữu VÀ
        // thành viên trong result_document_ids của chính bản ghi log đó —
        // không nới lỏng gì ở đây, chỉ bọc try/catch để một lỗi ghi nhận
        // click không biến thành một lỗi "không mở được văn bản".
        const logId = this.state.result.log_id;
        if (logId) {
            try {
                await this.orm.call("aidt.search.log", "action_click", [[logId], documentId]);
            } catch (err) {
                console.error("Không ghi nhận được lượt click vào nhật ký tìm kiếm:", err);
            }
        }
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
