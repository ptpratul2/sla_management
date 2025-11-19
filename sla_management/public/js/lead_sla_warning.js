// Copyright (c) 2024, SLA Management Team and contributors
// For license information, please see license.txt

frappe.ui.form.on("Lead", {
	refresh(frm) {
		if (frm.doc.last_stage_change_on && frm.doc.status) {
			const hours = frappe.datetime.get_hour_diff(
				frappe.datetime.now_datetime(),
				frm.doc.last_stage_change_on
			);
			
			// Show warning if in stage for more than 24 hours
			if (hours > 24) {
				frm.dashboard.set_headline_alert(
					`⚠️ SLA Alert: This Lead is in "${frm.doc.status}" for ${hours.toFixed(1)} hours.`,
					"red"
				);
			} else if (hours > 18) {
				// Show warning if approaching 24 hours
				frm.dashboard.set_headline_alert(
					`⚠️ SLA Warning: This Lead is in "${frm.doc.status}" for ${hours.toFixed(1)} hours.`,
					"orange"
				);
			}
		}
	}
});



