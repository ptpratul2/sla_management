// Copyright (c) 2024, SLA Management Team and contributors
// For license information, please see license.txt

frappe.ui.form.on("Opportunity", {
	refresh(frm) {
		if (frm.doc.last_stage_change_on && frm.doc.stage) {
			const hours = frappe.datetime.get_hour_diff(
				frappe.datetime.now_datetime(),
				frm.doc.last_stage_change_on
			);
			
			// Show warning if in stage for more than 48 hours
			if (hours > 48) {
				frm.dashboard.set_headline_alert(
					`⚠️ SLA Alert: This Opportunity is in stage "${frm.doc.stage}" for ${hours.toFixed(1)} hours.`,
					"red"
				);
			} else if (hours > 40) {
				// Show warning if approaching 48 hours
				frm.dashboard.set_headline_alert(
					`⚠️ SLA Warning: This Opportunity is in stage "${frm.doc.stage}" for ${hours.toFixed(1)} hours.`,
					"orange"
				);
			}
		}
	}
});



