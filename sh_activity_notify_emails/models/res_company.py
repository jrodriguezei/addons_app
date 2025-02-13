# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    activity_email_notification = fields.Boolean()

    edit_notification = fields.Boolean()
    done_notification = fields.Boolean()
    cancel_notification = fields.Boolean()

    notify_create_user_edit = fields.Boolean(" Notify Create User")
    notify_create_user_done = fields.Boolean("Notify Create User ")
    notify_create_user_cancel = fields.Boolean(" Notify Create User ")

    notify_assignee_user_edit = fields.Boolean(" Notify Assignee User")
    notify_assignee_user_done = fields.Boolean("Notify Assignee User ")
    notify_assignee_user_cancel = fields.Boolean(" Notify Assignee User ")
