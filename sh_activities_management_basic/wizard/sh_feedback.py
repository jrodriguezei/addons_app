# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields, _
from odoo.tools.misc import clean_context


class ActivityFeedback(models.TransientModel):
    _name = 'activity.feedback'
    _description = 'Activity Feedback'

    feedback = fields.Text("Feedback",required=True)
    done_button_pressed = fields.Boolean()

    def action_done(self):
        active_id = self.env.context.get('active_id')
        activity_id = self.env['mail.activity'].sudo().browse(active_id)
        activity_id.state='done'
        activity_id.active=False
        activity_id.activity_done = True
        activity_id.date_done = fields.Date.today()
        activity_id.feedback = self.feedback
        activity_id._compute_state()
        messages = self.env['mail.message']
        record = self.env[activity_id.res_model].sudo().browse(activity_id.res_id)        
        record.sudo().message_post_with_source(
               'mail.message_activity_done',
                attachment_ids=[],
                render_values={
                    'activity': activity_id,
                    'feedback': self.feedback,
                    'display_assignee': activity_id.user_id != self.env.user
                },
                mail_activity_type_id=activity_id.activity_type_id.id,
                subtype_xmlid='mail.mt_activities',
            )
        messages |= record.sudo().message_ids[0]

    def action_schedule_done(self):
        active_id = self.env.context.get('active_id')
        activity_id = self.env['mail.activity'].sudo().browse(active_id)
        activity_id.state='done'
        activity_id.active=False
        activity_id.activity_done = True
        activity_id._compute_state()
        activity_id.date_done = fields.Date.today()
        activity_id.feedback = self.feedback
        ctx = dict(
            clean_context(self.env.context),
            default_previous_activity_type_id=activity_id.activity_type_id.id,
            activity_previous_deadline=activity_id.date_deadline,
            default_res_id=activity_id.res_id,
            default_res_model=activity_id.res_model,
        )
        messages, next_activities = activity_id._action_done(feedback=self.feedback)
        if next_activities:
            return False
        return {
            'name': _('Schedule an Activity'),
            'context': ctx,
            'view_mode': 'form',
            'res_model': 'mail.activity',
            'views': [(False, 'form')],
            'type': 'ir.actions.act_window',
            'target': 'new',
        }

