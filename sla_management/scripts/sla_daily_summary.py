# Copyright (c) 2024, SLA Management Team and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import now_datetime, add_days, get_datetime
from frappe import _


def sla_daily_summary():
	"""
	Daily scheduled job (runs at 7 AM) to send email summaries of SLA breaches.
	Groups breaches by reporting manager and sends consolidated emails.
	"""
	frappe.logger().info("Starting SLA Daily Summary...")
	
	# Get breaches from last 24 hours
	from_date = add_days(now_datetime(), -1)
	
	breaches = frappe.get_all(
		"SLA Breach Log",
		filters={
			"breached_on": [">=", from_date]
		},
		fields=["name", "vertical", "doctype_name", "record_id", "breached_by", 
				"stage", "hours_exceeded", "breached_on", "boss_email"],
		order_by="boss_email, breached_on"
	)
	
	if not breaches:
		frappe.logger().info("No SLA breaches in the last 24 hours.")
		return
	
	# Group breaches by boss_email
	breaches_by_boss = {}
	for breach in breaches:
		boss_email = breach.boss_email or "crm-head@promptpersonnel.com"
		if boss_email not in breaches_by_boss:
			breaches_by_boss[boss_email] = []
		breaches_by_boss[boss_email].append(breach)
	
	# Send email to each boss
	for boss_email, boss_breaches in breaches_by_boss.items():
		try:
			# Get user for boss_email
			boss_user = frappe.db.get_value("User", {"email": boss_email}, "name")
			
			if not boss_user:
				frappe.logger().warning(f"User not found for email: {boss_email}")
				continue
			
			# Prepare email content
			subject = _("Daily SLA Breach Summary - {0} Breaches").format(len(boss_breaches))
			
			# Build HTML table
			table_rows = []
			table_rows.append("<tr><th>Record</th><th>Vertical</th><th>Stage</th><th>Hours Exceeded</th><th>Breached By</th><th>Breached On</th></tr>")
			
			for breach in boss_breaches:
				record_link = f'<a href="/app/{breach.doctype_name.lower()}/{breach.record_id}">{breach.record_id}</a>'
				table_rows.append(
					f"<tr>"
					f"<td>{record_link}</td>"
					f"<td>{breach.vertical or '-'}</td>"
					f"<td>{breach.stage}</td>"
					f"<td>{breach.hours_exceeded:.1f}</td>"
					f"<td>{breach.breached_by}</td>"
					f"<td>{get_datetime(breach.breached_on).strftime('%Y-%m-%d %H:%M')}</td>"
					f"</tr>"
				)
			
			html_content = f"""
			<div style="font-family: Arial, sans-serif;">
				<h2>Daily SLA Breach Summary</h2>
				<p>You have <strong>{len(boss_breaches)}</strong> SLA breach(es) in the last 24 hours:</p>
				<table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse; width: 100%;">
					{''.join(table_rows)}
				</table>
				<p style="margin-top: 20px;">
					<small>This is an automated email from the SLA Management system.</small>
				</p>
			</div>
			"""
			
			# Send email
			frappe.sendmail(
				recipients=[boss_email],
				subject=subject,
				message=html_content,
				now=True
			)
			
			frappe.logger().info(f"Sent daily summary to {boss_email} ({len(boss_breaches)} breaches)")
			
		except Exception as e:
			frappe.logger().error(f"Failed to send daily summary to {boss_email}: {e}")
	
	frappe.logger().info("SLA Daily Summary completed.")
	return len(breaches)



