/** @odoo-module **/

import {ProgressBarField,progressBarField} from "@web/views/fields/progress_bar/progress_bar_field";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";

export class AutoRefreshProgressBarField extends ProgressBarField {
    setup() {
        super.setup();
        this.orm = useService("orm");// ORM service for data fetching
        this.bus = this.env.services["bus_service"];// Bus service for event handling
        this.refreshHandler = () => {
            this.reloadProgress();
        };

        this.startAutoRefresh();
    }

    startAutoRefresh() {
        if (document.autoRefreshSocket && document.refreshHandlers) {
            document.refreshHandlers.push(this.refreshHandler);
        } else {
            document.refreshHandlers = [this.refreshHandler];
            this.bus.addChannel("refresh_progress_bar");
            this.bus.subscribe("reload_data", (payload) => {
                document.refreshHandlers.forEach(handler => handler());
            });
            this.bus.start();
            document.autoRefreshSocket = true;
        }
    }

    async reloadProgress() {
        try {
            // Fetch updated record data from ORM
            if (!this.props.record || !this.props.record.data) {
                console.error("Record data is missing in props!", this.props);
                return;
            }

            const result = await this.orm.read(
                this.props.record.resModel || this.props.record.model, // Model name
                [this.props.record.resId || this.props.record.id],   // Record ID
                [this.props.name]  // Field name
            );

            if (result && result.length > 0) {
                const newValue = result[0][this.props.name];
                this.updateProgress(newValue);
            }
        } catch (error) {
            if (this.autoRefreshInterval) {
                clearInterval(this.autoRefreshInterval);
            } else {
                console.error("Error refreshing progress bar:", error);
            }
        }
    }

    updateProgress(newValue) {
        // Update the progress bar value
        this.props.record.data[this.currentValueField] = newValue;
        this.render();
    }

    destroy() {
        // Clean up the handler when the widget is destroyed
        document.refreshHandlers = document.refreshHandlers.filter(handler => handler !== this.refreshHandler);
        super.destroy();
    }
}

const autoProgressBarField = progressBarField;
autoProgressBarField.component = AutoRefreshProgressBarField;
// Register the extended field widget
registry.category("fields").add("auto_refresh_progress_bar",
    autoProgressBarField);