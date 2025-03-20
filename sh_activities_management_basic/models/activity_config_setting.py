# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    sh_planned_table = fields.Integer(default=10)
    sh_all_table = fields.Integer(default=10)
    sh_completed_table = fields.Integer(default=10)
    sh_due_table = fields.Integer(default=10)
    sh_cancel_table = fields.Integer(default=10)
    sh_display_multi_user = fields.Boolean()
    sh_display_all_activities_counter = fields.Boolean(default=True)
    sh_display_planned_activities_counter = fields.Boolean(default=True)
    sh_display_completed_activities_counter = fields.Boolean(default=True)
    sh_display_overdue_activities_counter = fields.Boolean(default=True)
    sh_display_cancelled_activities_counter = fields.Boolean(default=True)
    sh_display_all_activities_table = fields.Boolean(default=True)
    sh_display_planned_activities_table = fields.Boolean(default=True)
    sh_display_completed_activities_table = fields.Boolean(default=True)
    sh_display_overdue_activities_table = fields.Boolean(default=True)
    sh_display_cancelled_activities_table = fields.Boolean(default=True)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    sh_planned_table = fields.Integer(
        'Planned Activities Table Limit', related='company_id.sh_planned_table',readonly=False)
    sh_all_table = fields.Integer(
        'All Activities Table Limit', related='company_id.sh_all_table',readonly=False)
    sh_completed_table = fields.Integer(
        'Completed Activities Table Limit', related='company_id.sh_completed_table',readonly=False)
    sh_due_table = fields.Integer(
        'Due Activities Table Limit', related='company_id.sh_due_table',readonly=False)
    sh_cancel_table = fields.Integer('Cancelled Activities Table Limit', related='company_id.sh_cancel_table',readonly=False)
    sh_display_multi_user = fields.Boolean('Display Multi Users ?',related='company_id.sh_display_multi_user',readonly=False)
    sh_display_all_activities_counter = fields.Boolean('All Activities ',related='company_id.sh_display_all_activities_counter',readonly=False)
    sh_display_planned_activities_counter = fields.Boolean('Planned Activities ',related='company_id.sh_display_planned_activities_counter',readonly=False)
    sh_display_completed_activities_counter = fields.Boolean('Completed Activities ',related='company_id.sh_display_completed_activities_counter',readonly=False)
    sh_display_overdue_activities_counter = fields.Boolean('Overdue Activities ',related='company_id.sh_display_overdue_activities_counter',readonly=False)
    sh_display_cancelled_activities_counter = fields.Boolean('Cancelled Activities ',related='company_id.sh_display_cancelled_activities_counter',readonly=False)
    sh_display_all_activities_table = fields.Boolean('All Activities',related='company_id.sh_display_all_activities_table',readonly=False)
    sh_display_planned_activities_table = fields.Boolean('Planned Activities',related='company_id.sh_display_planned_activities_table',readonly=False)
    sh_display_completed_activities_table = fields.Boolean('Completed Activities',related='company_id.sh_display_completed_activities_table',readonly=False)
    sh_display_overdue_activities_table = fields.Boolean('Overdue Activities',related='company_id.sh_display_overdue_activities_table',readonly=False)
    sh_display_cancelled_activities_table = fields.Boolean('Cancelled Activities',related='company_id.sh_display_cancelled_activities_table',readonly=False)
    
    def action_update_activity_data(self):
        activities = self.env['mail.activity'].sudo().search([('active','!=',False),('activity_cancel','=',False),('activity_done','=',False)])
        if activities:
            for activity in activities:
                activity.active = True
                activity.onchange_state()
