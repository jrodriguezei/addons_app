# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    check_user_activity = fields.Boolean(
        string='Checl User Activity', compute="_compute_check_user_activity_type"
    )

    check_user_activity_type = fields.Selection([
        ('none', 'none'),
        ('user', 'user'),
        ('manager', 'manager'),
        ('supervisor', 'supervisor'),
    ],
        string='check user activity type', default="none")

    def _compute_check_user_activity_type(self):
        for rec in self:
            rec.check_user_activity = True
            if rec.has_group('sh_activities_management_basic.group_activity_supervisor'):
                rec.check_user_activity_type = 'supervisor'
            if not rec.has_group('sh_activities_management_basic.group_activity_supervisor') and not rec.has_group('sh_activities_management_basic.group_activity_manager') and rec.has_group('sh_activities_management_basic.group_activity_user'):
                rec.check_user_activity_type = 'user'
            if rec.has_group('sh_activities_management_basic.group_activity_manager'):
                rec.check_user_activity_type = 'manager'
