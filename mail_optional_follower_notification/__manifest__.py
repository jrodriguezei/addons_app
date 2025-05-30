# Copyright 2016 ACSONE SA/NV (<http://acsone.eu>)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Mail optional follower notification",
    "summary": "Choose to notify followers on mail.compose.message",
    "author": "ACSONE SA/NV," "Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/social",
    "category": "Social Network",
    "version": "17.0.1.1.0",
    "license": "AGPL-3",
    "depends": ["mail","account"],
    "data": [
        "views/res_config_settings_view.xml",
        "wizard/mail_compose_message_view.xml",
    ],
}
