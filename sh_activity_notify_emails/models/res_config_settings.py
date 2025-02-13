# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    activity_email_notification = fields.Boolean(
        related='company_id.activity_email_notification', readonly=False)

    edit_notification = fields.Boolean(
        related='company_id.edit_notification', readonly=False)
    done_notification = fields.Boolean(
        related='company_id.done_notification', readonly=False)
    cancel_notification = fields.Boolean(
        related='company_id.cancel_notification', readonly=False)

    notify_create_user_edit = fields.Boolean(
        " Notify Create User", related='company_id.notify_create_user_edit', readonly=False)
    notify_create_user_done = fields.Boolean(
        "Notify Create User ", related='company_id.notify_create_user_done', readonly=False)
    notify_create_user_cancel = fields.Boolean(
        " Notify Create User ", related='company_id.notify_create_user_cancel', readonly=False)

    notify_assignee_user_edit = fields.Boolean(
        " Notify Assignee User", related='company_id.notify_assignee_user_edit', readonly=False)
    notify_assignee_user_done = fields.Boolean(
        "Notify Assignee User ", related='company_id.notify_assignee_user_done', readonly=False)
    notify_assignee_user_cancel = fields.Boolean(
        " Notify Assignee User ", related='company_id.notify_assignee_user_cancel', readonly=False)
