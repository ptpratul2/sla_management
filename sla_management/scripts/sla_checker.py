

# Copyright (c) 2024
# SLA Management App

import frappe
from frappe.utils import now_datetime, get_datetime, time_diff_in_hours


def map_sla_vertical_to_record_vertical(sla_vertical):
    mapping = {
        "Permanent Staffing": "Permanent Staffing",
        "Temporary Staffing": "Temporary Staffing"
    }
    return mapping.get(sla_vertical, sla_vertical)


def get_reporting_manager_email(employee_name, vertical):
    manager_email = frappe.db.get_value(
        "CRM Reporting Hierarchy", 
        {"full_name": employee_name, "department": vertical}, 
        "reporting_manager_email"
    )
    return manager_email


def send_sla_notification(user, doctype, docname, stage, hours_spent, hours_exceeded):
    try:
        noti = frappe.new_doc("Notification Log")
        noti.for_user = user
        noti.type = "Alert"
        noti.document_type = doctype
        noti.document_name = docname
        noti.subject = f"SLA Breach Alert: {docname}"
        noti.email_content = (
            f"SLA Breach: Record is in stage '{stage}' for "
            f"{hours_spent:.1f} hours (exceeded by {hours_exceeded:.1f} hours)."
        )
        noti.insert(ignore_permissions=True)
    except Exception as e:
        frappe.logger().error(f"SLA Notification failed: {e}")


def sla_checker():
    frappe.logger().info("Starting SLA Checker...")

    ALLOWED_VERTICALS = ["Permanent Staffing", "Temporary Staffing"]
    ALLOWED_OPPORTUNITY_STAGES = ["Introduction", "Discussion", "Proposal", "Negotiation"]

    # 1. 'message' field ko query mein add kiya gaya hai
    active_rules = frappe.get_all(
        "SLA Rule",
        filters={"active": 1},
        fields=[
            "name",
            "vertical",
            "applies_to",
            "max_hours_allowed",
            "message"  # <--- Added this
        ]
    )

    if not active_rules:
        return 0

    current_time = now_datetime()
    breach_count = 0

    for rule in active_rules:
        if rule.vertical not in ALLOWED_VERTICALS:
            continue

        record_vertical = map_sla_vertical_to_record_vertical(rule.vertical)

        if rule.applies_to == "Lead":
            
            # --- RULE-1: Lead New ---
            leads_new = frappe.get_all(
                "Lead",
                filters={"status": "New", "custom_vertical": record_vertical},
                fields=["name", "owner", "creation"]
            )

            for lead in leads_new:
                sla_start = get_datetime(lead.creation)
                hours_spent = time_diff_in_hours(current_time, sla_start)

                if hours_spent <= rule.max_hours_allowed:
                    continue

                if frappe.db.exists("SLA Breach Log", {"doctype_name": "Lead", "record_id": lead.name, "stage": "New"}):
                    continue

                hours_exceeded = hours_spent - rule.max_hours_allowed
                mgr_email = get_reporting_manager_email(lead.owner, record_vertical)

                # 2. Log mein 'message' copy kiya gaya hai
                frappe.get_doc({
                    "doctype": "SLA Breach Log",
                    "vertical": record_vertical,
                    "doctype_name": "Lead",
                    "record_id": lead.name,
                    "breached_by": lead.owner,
                    "stage": "New",
                    "hours_exceeded": hours_exceeded,
                    "last_stage_change_on": sla_start,
                    "breached_on": current_time,
                    "reporting_manager_email": mgr_email or "",
                    "message": rule.message  # <--- Rule se message log mein gaya
                }).insert(ignore_permissions=True)

                send_sla_notification(lead.owner, "Lead", lead.name, "New", hours_spent, hours_exceeded)
                breach_count += 1
                frappe.db.commit()

            # --- RULE-2: Lead Converted ---
            leads_converted = frappe.get_all(
                "Lead",
                filters={"status": "Converted", "custom_vertical": record_vertical},
                fields=["name", "owner", "creation"]
            )

            for lead in leads_converted:
                sla_start = get_datetime(lead.creation)
                hours_spent = time_diff_in_hours(current_time, sla_start)
                if hours_spent <= rule.max_hours_allowed:
                    continue

                opp = frappe.db.get_value("Opportunity", {"opportunity_from": "Lead", "party_name": lead.name}, ["name", "creation"], as_dict=True)
                if opp:
                    if time_diff_in_hours(get_datetime(opp.creation), sla_start) <= rule.max_hours_allowed:
                        continue

                if frappe.db.exists("SLA Breach Log", {"doctype_name": "Lead", "record_id": lead.name, "stage": "Converted"}):
                    continue

                hours_exceeded = hours_spent - rule.max_hours_allowed
                mgr_email = get_reporting_manager_email(lead.owner, record_vertical)

                # Log mein 'message' copy kiya gaya
                frappe.get_doc({
                    "doctype": "SLA Breach Log",
                    "vertical": record_vertical,
                    "doctype_name": "Lead",
                    "record_id": lead.name,
                    "breached_by": lead.owner,
                    "stage": "Converted",
                    "hours_exceeded": hours_exceeded,
                    "last_stage_change_on": sla_start,
                    "breached_on": current_time,
                    "reporting_manager_email": mgr_email or "",
                    "message": rule.message  # <--- Added
                }).insert(ignore_permissions=True)

                send_sla_notification(lead.owner, "Lead", lead.name, "Converted", hours_spent, hours_exceeded)
                breach_count += 1
                frappe.db.commit()

        # =====================================================
        # RULE-3 → OPPORTUNITY
        # =====================================================
        elif rule.applies_to == "Opportunity":
            opportunities = frappe.get_all(
                "Opportunity",
                filters={"status": ["in", ALLOWED_OPPORTUNITY_STAGES], "custom_vertical": record_vertical},
                fields=["name", "owner", "status", "creation"]
            )

            for opp in opportunities:
                sla_start = get_datetime(opp.creation)
                hours_spent = time_diff_in_hours(current_time, sla_start)

                if hours_spent <= rule.max_hours_allowed:
                    continue

                if frappe.db.exists("SLA Breach Log", {"doctype_name": "Opportunity", "record_id": opp.name, "stage": opp.status}):
                    continue

                hours_exceeded = hours_spent - rule.max_hours_allowed
                mgr_email = get_reporting_manager_email(opp.owner, record_vertical)

                # Log mein 'message' copy kiya gaya
                frappe.get_doc({
                    "doctype": "SLA Breach Log",
                    "vertical": record_vertical,
                    "doctype_name": "Opportunity",
                    "record_id": opp.name,
                    "breached_by": opp.owner,
                    "stage": opp.status,
                    "hours_exceeded": hours_exceeded,
                    "last_stage_change_on": sla_start,
                    "breached_on": current_time,
                    "reporting_manager_email": mgr_email or "",
                    "message": rule.message  # <--- Added
                }).insert(ignore_permissions=True)

                send_sla_notification(opp.owner, "Opportunity", opp.name, opp.status, hours_spent, hours_exceeded)
                breach_count += 1
                frappe.db.commit()

    frappe.logger().info(f"SLA Checker Done. Total Breaches: {breach_count}")
    return breach_count