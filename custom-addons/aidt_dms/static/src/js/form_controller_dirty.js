/** @odoo-module **/

import { FormController } from "@web/views/form/form_controller";
import { patch } from "@web/core/utils/patch";
import { onMounted } from "@odoo/owl";

patch(FormController.prototype, "aidt_dms.form_controller_dirty", {
    setup() {
        this._super.apply(this, arguments);
        onMounted(() => {
            if (this.props && this.props.context && this.props.context.mark_ocr_dirty) {
                if (this.model && this.model.root) {
                    // Mark the form record as dirty so Odoo's canLeave / navigation handler
                    // prompts the user "Unsaved changes: Do you want to save or discard?"
                    this.model.root.isDirty = true;
                }
            }
        });
    },
});
