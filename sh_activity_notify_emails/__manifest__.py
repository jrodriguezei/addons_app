# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
{
    "name": "Activity Email Notification | Activity Mail Notification",
    "author": "Softhealer Technologies",
    "license": "OPL-1",
    "website": "https://www.softhealer.com",
    "support": "support@softhealer.com",
    "category": "Discuss",
    "summary": "Activity Mail Notifier Module,Send Activity Notification, Activity Email Notification Salesperson, Activity Notification Customer, Reminder For Activity, Fix Activity Notification, Schedule Activity And Notification, Notification Management Odoo",
    "description": """
This module used to send activity email notifications to create a user or assign user. You can enable email notifications on activity edit, cancel, done. You can also enable/disable send email notifications to created users or assign users.

 Activity Email Notification Odoo
 Activity Email Notifier Module, Send Salesperson Notification Before Activity, Send Customer Notification After Activity, Notify Customer For Activity Due Date, Mail Reminder For Activity Odoo.
 Activity Email  Notifier Module, Salesperson Activity Email Notification, Customer Activity Mail Notification Module,Activity Due Date Mail Notify, Activity Email Reminder Odoo""",
    "version": "0.0.2",
    "depends": ["mail","crm"],
    "application": True,
    "data": [
        "data/mail_template_data.xml",
        "views/res_config_settings_views.xml"
    ],

    "images": ["static/description/background.png", ],
    "auto_install": False,
    "installable": True,
    "price": 30,
    "currency": "EUR"
}
