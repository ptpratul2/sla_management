

# Copyright (c) 2024
# SLA Management App

import frappe
from frappe.utils import now_datetime, add_days, get_datetime
from frappe import _


def sla_daily_summary():
    """
    Daily Scheduled Job (Runs at 7 AM)
    """

    frappe.logger().info("Starting SLA Daily Summary...")

    # 1. Verticals filter
    ALLOWED_VERTICALS = [
        "Permanent Staffing",
        "Temporary Staffing"
    ]

    # 2. Pichle 24 ghante ka filter
    from_date = add_days(now_datetime(), -1)

    # 3. Fetching Breaches (Added "message" in fields)
    breaches = frappe.get_all(
        "SLA Breach Log",
        filters={
            "breached_on": [">=", from_date],
            "vertical": ["in", ALLOWED_VERTICALS]
        },
        fields=[
            "name",
            "vertical",
            "doctype_name",
            "record_id",
            "breached_by",
            "stage",
            "hours_exceeded",
            "breached_on",
            "reporting_manager_email",
            "message"  # <--- Added message field
        ]
    )

    if not breaches:
        frappe.logger().info("No SLA breaches found in the last 24 hours.")
        return 0

    # 4. Grouping Breaches by Manager Email
    breaches_by_manager = {}
    
    for breach in breaches:
        email = breach.reporting_manager_email or "crm-head@promptpersonnel.com"
        
        if email not in breaches_by_manager:
            breaches_by_manager[email] = []
        
        breaches_by_manager[email].append(breach)

    # 5. Sending Emails
    sent_count = 0
    for manager_email, manager_breaches in breaches_by_manager.items():
        try:
            subject = _("Daily SLA Breach Summary: {0} Records").format(len(manager_breaches))

            # Table Header (Added Message Column)
            rows = [
                """<tr style="background-color: #f8f9fa;">
                    <th style="border: 1px solid #ddd; padding: 8px;">Record ID</th>
                    <th style="border: 1px solid #ddd; padding: 8px;">Vertical</th>
                    <th style="border: 1px solid #ddd; padding: 8px;">Stage</th>
                    <th style="border: 1px solid #ddd; padding: 8px;">Exceeded (Hrs)</th>
                    <th style="border: 1px solid #ddd; padding: 8px;">Owner</th>
                    <th style="border: 1px solid #ddd; padding: 8px;">Message</th>
                    <th style="border: 1px solid #ddd; padding: 8px;">Breached On</th>
                </tr>"""
            ]

            # Table Data
            for b in manager_breaches:
                # Link generation
                record_url = f"/app/{b.doctype_name.lower().replace(' ', '-')}/{b.record_id}"
                
                # Handling None message
                msg_display = b.message if b.message else "-"

                rows.append(f"""
                <tr>
                    <td style="border: 1px solid #ddd; padding: 8px;"><a href="{record_url}">{b.record_id}</a></td>
                    <td style="border: 1px solid #ddd; padding: 8px;">{b.vertical}</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">{b.stage}</td>
                    <td style="border: 1px solid #ddd; padding: 8px; color: red;">{b.hours_exceeded:.1f}</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">{b.breached_by}</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">{msg_display}</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">{get_datetime(b.breached_on).strftime('%Y-%m-%d %I:%M %p')}</td>
                </tr>
                """)

            # Email Body HTML
            email_html = f"""
            <div style="font-family: sans-serif; color: #333;">
                <p>Hello,</p>
                <p>Below is the summary of SLA breaches that occurred in your vertical/team over the last 24 hours:</p>
                
                <table style="border-collapse: collapse; width: 100%; font-size: 12px;">
                    {''.join(rows)}
                </table>
                
                <p style="margin-top: 20px;">Please take necessary actions to clear the pending records.</p>
                <hr>
                <p><small>This is an automated system notification.</small></p>
            </div>
            """

            frappe.sendmail(
                recipients=[manager_email],
                subject=subject,
                message=email_html,
                now=True
            )
            sent_count += 1

        except Exception as e:
            frappe.logger().error(f"SLA Summary failed for {manager_email}: {e}")

    frappe.logger().info(f"SLA Daily Summary sent to {sent_count} managers.")
    return len(breaches)