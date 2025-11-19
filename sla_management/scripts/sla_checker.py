# Copyright (c) 2024, SLA Management Team and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import now_datetime, get_datetime, time_diff_in_hours
from frappe import _


def map_sla_vertical_to_record_vertical(sla_vertical, doctype):
	"""
	Map SLA Rule vertical values to Lead/Opportunity vertical values
	
	Args:
		sla_vertical: Vertical value from SLA Rule
		doctype: Lead or Opportunity
	
	Returns:
		Record vertical value
	"""
	# Lead uses different vertical values than SLA Rule
	if doctype == "Lead":
		mapping = {
			"Permanent Staffing": "Permanent",
			"Temporary Staffing": "Temporary",
			"Learning & Development": "L&D",
			"HR Consulting": "LLC",
			"Franchise": "Franchise",
			"Alliances/Partnerships": "LLC",
			"POSH": "LLC",
			"Labour Law Advisory & Compliance": "LLC"
		}
		return mapping.get(sla_vertical, sla_vertical)
	
	# For Opportunity, check if it uses same values as SLA Rule or different
	# For now, return as-is (can be updated if needed)
	return sla_vertical


def get_boss_email(user_email: str) -> str | None:
	"""
	Get reporting manager email from CRM Reporting Hierarchy.
	Falls back to default email if not found.
	"""
	if not user_email:
		return "crm-head@promptpersonnel.com"
	
	try:
		# Get user's email from User doctype if user_email is a username
		user_doc_email = frappe.db.get_value("User", user_email, "email")
		email_to_lookup = user_doc_email or user_email
		
		# Try to find in CRM Reporting Hierarchy
		hierarchy_list = frappe.get_all(
			"CRM Reporting Hierarchy",
			filters={"email": email_to_lookup},
			fields=["reporting_manager_email"],
			limit=1
		)
		
		if hierarchy_list and hierarchy_list[0].get("reporting_manager_email"):
			return hierarchy_list[0].get("reporting_manager_email")
	except Exception:
		pass
	
	# Fallback to default
	return "crm-head@promptpersonnel.com"


def sla_checker():
	"""
	Hourly scheduled job to check SLA breaches.
	Compares time in stage with allowed SLA hours.
	Sends in-app notifications and logs breaches.
	"""
	frappe.logger().info("Starting SLA Checker...")
	
	# Get all active SLA rules
	active_rules = frappe.get_all(
		"SLA Rule",
		filters={"active": 1},
		fields=["name", "vertical", "applies_to", "stage_field", "stage_value", 
				"max_hours_allowed", "notify_to", "escalate_to"]
	)
	
	if not active_rules:
		frappe.logger().info("No active SLA rules found.")
		return
	
	breach_count = 0
	
	for rule in active_rules:
		doctype = rule.applies_to
		stage_field = rule.stage_field
		stage_value = rule.stage_value
		vertical = rule.vertical
		max_hours = rule.max_hours_allowed
		
		# Build filters
		filters = {
			stage_field: stage_value,
			"last_stage_change_on": ["is", "set"]
		}
		
		# Add vertical filter if vertical field exists
		# Check if vertical field exists in the doctype
		try:
			meta = frappe.get_meta(doctype)
			if meta.has_field("vertical"):
				# Map SLA vertical to record vertical (Lead uses different values)
				record_vertical = map_sla_vertical_to_record_vertical(vertical, doctype)
				filters["vertical"] = record_vertical
		except Exception:
			pass
		
		# Get all records matching the rule
		records = frappe.get_all(
			doctype,
			filters=filters,
			fields=["name", "owner", stage_field, "last_stage_change_on", "vertical"]
		)
		
		current_time = now_datetime()
		
		for record in records:
			if not record.last_stage_change_on:
				continue
			
			last_change = get_datetime(record.last_stage_change_on)
			hours_in_stage = time_diff_in_hours(current_time, last_change)
			
			# Check if SLA is breached
			if hours_in_stage > max_hours:
				hours_exceeded = hours_in_stage - max_hours
				
				# Check if breach already logged (to avoid duplicates)
				existing_breach = frappe.db.exists(
					"SLA Breach Log",
					{
						"doctype_name": doctype,
						"record_id": record.name,
						"stage": stage_value,
						"breached_on": [">=", last_change]
					}
				)
				
				if existing_breach:
					continue
				
				# Get boss email
				boss_email = get_boss_email(record.owner)
				
				# Create breach log
				breach_log = frappe.get_doc({
					"doctype": "SLA Breach Log",
					"vertical": record.get("vertical") or vertical,
					"doctype_name": doctype,
					"record_id": record.name,
					"breached_by": record.owner,
					"stage": stage_value,
					"hours_exceeded": hours_exceeded,
					"last_stage_change_on": last_change,
					"breached_on": current_time,
					"boss_email": boss_email
				})
				breach_log.insert(ignore_permissions=True)
				
				# Send in-app notification to owner
				try:
					notification_doc = frappe.new_doc("Notification Log")
					notification_doc.for_user = record.owner
					notification_doc.type = "Alert"
					notification_doc.document_type = doctype
					notification_doc.document_name = record.name
					notification_doc.subject = _("SLA Breach Alert: {0}").format(record.name)
					notification_doc.email_content = _(
						"SLA Breach: {0} has been in stage '{1}' for {2:.1f} hours "
						"(exceeded by {3:.1f} hours)."
					).format(record.name, stage_value, hours_in_stage, hours_exceeded)
					notification_doc.insert(ignore_permissions=True)
				except Exception as e:
					frappe.logger().error(f"Failed to send notification: {e}")
				
				# Send notification to additional recipients if specified
				if rule.notify_to:
					notify_emails = [email.strip() for email in rule.notify_to.split(",") if email.strip()]
					for email in notify_emails:
						try:
							user = frappe.db.get_value("User", {"email": email}, "name")
							if user:
								notification_doc = frappe.new_doc("Notification Log")
								notification_doc.for_user = user
								notification_doc.type = "Alert"
								notification_doc.document_type = doctype
								notification_doc.document_name = record.name
								notification_doc.subject = _("SLA Breach Alert: {0}").format(record.name)
								notification_doc.email_content = _(
									"SLA Breach: {0} has been in stage '{1}' for {2:.1f} hours "
									"(exceeded by {3:.1f} hours)."
								).format(record.name, stage_value, hours_in_stage, hours_exceeded)
								notification_doc.insert(ignore_permissions=True)
						except Exception as e:
							frappe.logger().error(f"Failed to send notification to {email}: {e}")
				
				breach_count += 1
				frappe.db.commit()
	
	frappe.logger().info(f"SLA Checker completed. Found {breach_count} breaches.")
	return breach_count

