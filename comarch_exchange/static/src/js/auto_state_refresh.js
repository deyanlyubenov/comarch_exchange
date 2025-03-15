/** @odoo-module **/

import {Component} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";
import {useState} from "@odoo/owl";


export class AutoStateRefresh extends Component {
    setup() {
        this.state = useState({
            currentValue: this.getCurrentValue(this.props),
        });
        this.orm = useService("orm");
        this.bus = this.env.services["bus_service"];// Bus service for event handling
        this.refreshHandler = () => {
            this.reloadState();
        };

        this.startAutoRefresh();
    }

    getCurrentValue(p) {
        return p.record.data[this.getCurrentValueField(p)] || '';
    }

    getCurrentValueField(p) {
        return typeof p.currentValueField === "string" ? p.currentValueField : p.name;
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

    async reloadState() {
        try {
            // Fetch updated record data from ORM
            if (!this.props.record || !this.props.record.data) {
                console.error("Record data is missing in props!", this.props);
                return;
            }

            const result = await this.orm.read(
                this.props.record.resModel || this.props.record.model, // Model name
                [this.props.record.resId || this.props.record.id],   // Record ID
                [this.props.name]
            );

            if (result && result.length > 0) {
                const newValue = result[0][this.props.name];
                this.updateState(newValue);
            }
        } catch (error) {
            console.error("Error refreshing status bar:", error);
        }
    }

    updateState(newValue) {
        if (this.state.currentValue === newValue) {
            return;
        }
        this.state.currentValue = newValue;
        document.location.reload();
    }

    destroy() {
        document.refreshHandlers = document.refreshHandlers.filter(handler => handler !== this.refreshHandler);
        super.destroy();
    }
}

AutoStateRefresh.template = "comarch_exchange.auto_refresh_field";

registry.category("fields").add("auto_refresh_field",
    {
        component: AutoStateRefresh,
        props: {},
    });
