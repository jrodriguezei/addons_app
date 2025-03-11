# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields, api, modules, exceptions, _, Command
from datetime import datetime
from odoo.osv import expression
from dateutil.relativedelta import relativedelta
from odoo.tools.misc import clean_context
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
from odoo.tools import html2plaintext
import math
import json
from odoo.exceptions import UserError
from collections import defaultdict
from odoo.http import request
import logging
_logger = logging.getLogger(__name__)
from odoo.tools import SQL
import pytz

class MailActivityMixin(models.AbstractModel):
    _inherit = 'mail.activity.mixin'

    def _read_group_groupby(self, groupby_spec, query):
        if groupby_spec != 'activity_state':
            return super()._read_group_groupby(groupby_spec, query)

        self.env['mail.activity'].flush_model(['res_model', 'res_id', 'user_id', 'date_deadline'])        

        tz = 'UTC'
        if self.env.context.get('tz') in pytz.all_timezones_set:
            tz = self.env.context['tz']

        sql_join = SQL(
            """
            (SELECT res_id,
                CASE
                    WHEN min(date_deadline - (now() AT TIME ZONE COALESCE(res_partner.tz, %(tz)s))::date) > 0 THEN 'planned'
                    WHEN min(date_deadline - (now() AT TIME ZONE COALESCE(res_partner.tz, %(tz)s))::date) < 0 THEN 'overdue'
                    WHEN min(date_deadline - (now() AT TIME ZONE COALESCE(res_partner.tz, %(tz)s))::date) = 0 THEN 'today'
                    ELSE null
                END AS activity_state
            FROM mail_activity
            JOIN res_users ON (res_users.id = mail_activity.user_id)
            JOIN res_partner ON (res_partner.id = res_users.partner_id)
            WHERE res_model = %(res_model)s and mail_activity.active = True
            GROUP BY res_id)
            """,
            res_model=self._name,
            tz=tz,
        )
        alias = query.join(self._table, "id", sql_join, "res_id", "last_activity_state")

        return SQL.identifier(alias, 'activity_state'), ['activity_state']



class MailActivity(models.Model):
    """ Inherited Mail Acitvity to add custom field"""
    _inherit = 'mail.activity'

    @api.model
    def default_company_id(self):
        return self.env.company

    active = fields.Boolean(default=True)
    supervisor_id = fields.Many2one('res.users', string="Supervisor",
                                    domain="[('check_user_activity_type', 'in', ['supervisor','manager'])]")
    sh_activity_tags = fields.Many2many(
        "sh.activity.tags", string='Activity Tags')
    state = fields.Selection(
        selection_add=[("done", "Done"), ("cancel", "Cancelled")],
        compute="_compute_state",
        search='_search_state'
    )
    sh_state = fields.Selection([('overdue', 'Overdue'), ('today', 'Today'), (
        'planned', 'Planned'), ('done', 'Done'), ('cancel', 'Cancelled')], string='State ')
    date_done = fields.Date("Completed Date", index=True, readonly=True)
    feedback = fields.Text("Feedback")

    text_note = fields.Char("Notes In Char format ",
                            compute='_compute_html_to_char_note')
    sh_user_ids = fields.Many2many('res.users', string="Assign Multi Users")
    sh_display_multi_user = fields.Boolean(
        compute='_compute_sh_display_multi_user')
    company_id = fields.Many2one(
        'res.company', string='Company', default=default_company_id)
    color = fields.Integer('Color Index', default=0)
    sh_create_individual_activity = fields.Boolean(
        'Individual activities for multi users ?')
    activity_cancel = fields.Boolean()
    activity_done = fields.Boolean()

    reference = fields.Reference(string='Related Document',
                                 selection='_reference_models')

    @api.model
    def _reference_models(self):
        models = self.env['ir.model'].sudo().search(
            [('state', '!=', 'manual')])
        return [(model.model, model.name)
                for model in models
                if not model.model.startswith('ir.')]

    @api.onchange('reference')
    def onchange_reference(self):
        if self.reference:
            if self.reference._name:
                model_id = self.env['ir.model'].sudo().search(
                    [('model', '=', self.reference._name)], limit=1)
                if model_id:
                    self.res_model_id = model_id.id
                    self.res_id = self.reference.id
                    self.res_model = self.reference._name

    @api.depends('res_model', 'res_id')
    def _compute_res_name(self):
        for activity in self:
            activity.res_name = ''
            if activity.res_model and activity.res_id:
                activity.res_name = self.env[activity.res_model].browse(
                    activity.res_id).name_get()[0][1]

    @api.onchange('state')
    def onchange_state(self):
        self.ensure_one()
        self.activity_done = False
        self.activity_cancel = False
        self._compute_state()

    # ~ @api.depends('active', 'date_deadline')
    # ~ def _compute_state(self):
        # ~ super(MailActivity, self)._compute_state()

        # ~ for record in self.filtered(lambda activity: not activity.active):
            # ~ _logger.info('=================1================')
            # ~ _logger.info(record.state)
            # ~ if record.activity_cancel:
                # ~ record.state = 'cancel'
            # ~ if record.activity_done:
                # ~ record.state = 'done'
            # ~ _logger.info(record.state)
            # ~ _logger.info('================2=================')
            
        # ~ for activity_record in self.filtered(lambda activity: activity.active):
            # ~ activity_record.sh_state = activity_record.state


    @api.depends('active', 'date_deadline')
    def _compute_state(self):
        """Hereda y extiende el cálculo del estado de la actividad."""
        
        super()._compute_state()

        for record in self:
            if not record.active:
                _logger.info('=================1================')
                _logger.info(record.state)

                # Asegurar que `state` siempre tenga un valor
                if record.activity_cancel:
                    record.state = 'cancel'
                elif record.activity_done:
                    record.state = 'done'
                else:
                    record.state = 'pending'  # Asignar un valor por defecto
                
                _logger.info(record.state)
                _logger.info('================2=================')
            
            # Si el registro está activo
            else:
                record.sh_state = record.state or 'pending'  # Evitar valores vacíos


    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('res_model_id'):
                model_id = self.env['ir.model'].sudo().search([('id','=',vals.get('res_model_id'))],limit=1)
                if model_id:
                    if 'activity_ids' not in self.env[model_id.model]._fields:
                        raise UserError('You can not create activity for this model due to this model does not have activity field.')
        res_values = super(MailActivity, self).create(vals_list) 
        for res in res_values:         
            if res.sh_user_ids and res.sh_create_individual_activity:
                for user in res.sh_user_ids:
                    if res.user_id.id != user.id:
                        self.env['mail.activity'].sudo().create({
                            'user_id':user.id,
                            'res_model_id': res.res_model_id.id,
                            'res_id': res.res_id,
                            'date_deadline': res.date_deadline,
                            'supervisor_id': res.supervisor_id.id,
                            'activity_type_id': res.activity_type_id.id,
                            'summary': res.summary,
                            'sh_activity_tags': [(6, 0, res.sh_activity_tags.ids)],
                            'note': res.note,
                        })
                res.sh_user_ids = [(6,0,[])]
            try:
                if res.state:
                    res.sh_state = res.state
            except Exception:
                _logger.exception('No asignado state')
        return res_values

    def write(self, vals):
        if self:
            for rec in self:
                if vals.get('state'):
                    vals.update({
                        'sh_state': vals.get('state')
                    })
                if vals.get('active') and vals.get('active') == True:
                    rec.onchange_state()
        return super(MailActivity, self).write(vals)

    def _search_state(self, operator, value):
        not_done_ids = []
        done_ids = []
        if value == 'done':
            for record in self.search([('active', '=', False), ('date_done', '!=', False)]):
                done_ids.append(record.id)
        elif value == 'cancel':
            for record in self.search([('active', '=', False), ('date_done', '=', False)]):
                done_ids.append(record.id)
        elif value == 'today':
            for record in self.search([('date_deadline', '=', fields.Date.today())]):
                done_ids.append(record.id)
        elif value == 'planned':
            for record in self.search([('date_deadline', '>', fields.Date.today())]):
                done_ids.append(record.id)
        elif value == 'overdue':
            for record in self.search([('date_deadline', '<', fields.Date.today())]):
                done_ids.append(record.id)
        if operator == '=':
            return [('id', 'in', done_ids)]
        elif operator == 'in':
            return [('id', 'in', done_ids)]
        elif operator == '!=':
            return [('id', 'in', not_done_ids)]
        elif operator == 'not in':
            return [('id', 'in', not_done_ids)]
        else:
            return []

    def action_cancel(self):
        if self:
            for rec in self:
                rec.state = 'cancel'
                rec.active = False
                rec.date_done = False
                rec.activity_cancel = True
                rec._compute_state()

    def unarchive(self, active=True):
        self.ensure_one()
        self.activity_cancel = False
        self.active = True
        self._compute_state()

    @api.depends('company_id')
    def _compute_sh_display_multi_user(self):
        if self:
            for rec in self:
                rec.sh_display_multi_user = False
                if rec.company_id and rec.company_id.sh_display_multi_user:
                    rec.sh_display_multi_user = True

    def _compute_html_to_char_note(self):
        if self:
            for rec in self:
                if rec.note:
                    rec.text_note = html2plaintext(rec.note)
                else:
                    rec.text_note = ''

    def action_view_activity(self):
        self.ensure_one()
        try:
            self.env[self.res_model].browse(
                self.res_id).check_access_rule('read')
            return{
                'name': 'Origin Activity',
                'res_model': self.res_model,
                'res_id': self.res_id,
                'view_mode': 'form',
                'type': 'ir.actions.act_window',
                'target': 'current',
            }
        except exceptions.AccessError:
            raise exceptions.UserError(
                _('Assigned user %s has no access to the document and is not able to handle this activity.') %
                self.env.user.display_name)

    def action_edit_activity(self):
        self.ensure_one()
        view_id = self.env.ref(
            'sh_activities_management_basic.sh_mail_activity_type_view_form_inherit').id
        return {
            'name': _('Schedule an Activity'),
            'view_mode': 'form',
            'res_model': 'mail.activity',
            'views': [(view_id, 'form')],
            'res_id': self.id,
            'type': 'ir.actions.act_window',
            'target': 'new',
        }

    def action_done(self):
        """ Wrapper without feedback because web button add context as
        parameter, therefore setting context to feedback """
        return{
            'name': 'Activity Feedback',
            'res_model': 'activity.feedback',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'context': {'default_done_button_pressed': True},
            'target': 'new',
        }

    def action_done_from_popup(self, feedback=False):
        self.ensure_one()
        self = self.with_context(clean_context(self.env.context))
        messages, next_activities = self._action_done(
            feedback=feedback, attachment_ids=False)
        self.state = 'done'
        self.active = False
        self.activity_done = True
        if self.state == 'done':
            self.date_done = fields.Date.today()
        self.feedback = feedback
#         return messages.ids and messages.ids[0] or False

    def _action_done(self, feedback=False, attachment_ids=None):
        self.ensure_one()
        """ Private implementation of marking activity as done: posting a message, deleting activity
            (since done), and eventually create the automatical next activity (depending on config).
            :param feedback: optional feedback from user when marking activity as done
            :param attachment_ids: list of ir.attachment ids to attach to the posted mail.message
            :returns (messages, activities) where
                - messages is a recordset of posted mail.message
                - activities is a recordset of mail.activity of forced automically created activities
        """
        # marking as 'done'
        messages = self.env['mail.message']
        next_activities_values = []
        next_activities =None
        # Search for all attachments linked to the activities we are about to unlink. This way, we
        # can link them to the message posted and prevent their deletion.
        attachments = self.env['ir.attachment'].search_read([
            ('res_model', '=', self._name),
            ('res_id', 'in', self.ids),
        ], ['id', 'res_id'])

        activity_attachments = defaultdict(list)
        for attachment in attachments:
            activity_id = attachment['res_id']
            activity_attachments[activity_id].append(attachment['id'])

        for activity in self:
            # extract value to generate next activities
            if activity.chaining_type == 'trigger':
                Activity = self.env['mail.activity'].with_context(activity_previous_deadline=activity.date_deadline)  # context key is required in the onchange to set deadline
                vals = Activity.default_get(Activity.fields_get())

                vals.update({
                    'previous_activity_type_id': activity.activity_type_id.id,
                    'res_id': activity.res_id,
                    'res_model': activity.res_model,
                    'res_model_id': self.env['ir.model']._get(activity.res_model).id,
                })
                virtual_activity = Activity.new(vals)
                virtual_activity._onchange_previous_activity_type_id()
                virtual_activity._onchange_activity_type_id()
                next_activities_values.append(virtual_activity._convert_to_write(virtual_activity._cache))

            # post message on activity, before deleting it
            record = self.env[activity.res_model].browse(activity.res_id)            
            record.sudo().message_post_with_source(
               'mail.message_activity_done',
                attachment_ids=[],
                render_values={
                    'activity': activity,
                    'feedback': self.feedback,
                    'display_assignee': activity.user_id != self.env.user
                },
                mail_activity_type_id=activity.activity_type_id.id,
                subtype_xmlid='mail.mt_activities',
            )
            # Moving the attachments in the message
            # TODO: Fix void res_id on attachment when you create an activity with an image
            # directly, see route /web_editor/attachment/add
            activity_message = record.message_ids[0]
            message_attachments = self.env['ir.attachment'].browse(activity_attachments[activity.id])
            if message_attachments:
                message_attachments.write({
                    'res_id': activity_message.id,
                    'res_model': activity_message._name,
                })
                activity_message.attachment_ids = message_attachments
            messages |= activity_message
        if next_activities_values:
            next_activities = self.env['mail.activity'].create(next_activities_values)
        self.active = False
        self.date_done = fields.Date.today()
        self.feedback = feedback
        self.state = "done"
        self.activity_done = True
        self._compute_state()
        return messages, next_activities

    def action_done_schedule_next(self):
        """ Wrapper without feedback because web button add context as
        parameter, therefore setting context to feedback """
        return{
            'name': 'Activity Feedback',
            'res_model': 'activity.feedback',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'context': {'default_done_button_pressed': False},
            'target': 'new',
        }
#         return self.action_feedback_schedule_next()
    
    @api.model
    def action_done_dashboard(self,activity_id,activity_feedback):
        mail_activity_id = self.env['mail.activity'].sudo().browse(int(activity_id))
        if mail_activity_id:
            mail_activity_id.action_feedback(feedback = activity_feedback,attachment_ids=None)
            if mail_activity_id.state == 'done':
                return {'completed':True}

    def action_feedback(self, feedback=False, attachment_ids=None):       
        messages = False
        if self:
            messages, _next_activities = self.with_context(
                clean_context(self.env.context)
            )._action_done(feedback=feedback, attachment_ids=attachment_ids)
        return messages[0].id if messages else False
    
    def activity_format(self):
        self = self.filtered(lambda r: r.active == True)
        activities = self.read()
        mail_template_ids = set([template_id for activity in activities for template_id in activity["mail_template_ids"]])
        mail_template_info = self.env["mail.template"].browse(mail_template_ids).read(['id', 'name'])
        mail_template_dict = dict([(mail_template['id'], mail_template) for mail_template in mail_template_info])
        for activity in activities:
            activity['mail_template_ids'] = [mail_template_dict[mail_template_id] for mail_template_id in activity['mail_template_ids']]
        return activities

    
# class ResUsers(models.Model):
#     _inherit = 'res.users'

#     @api.model
#     def systray_get_activities(self):
#         # query = """SELECT m.id, count(*), act.res_model as model,
#         #                 CASE
#         #                     WHEN %(today)s::date - act.date_deadline::date = 0 Then 'today'
#         #                     WHEN %(today)s::date - act.date_deadline::date > 0 Then 'overdue'
#         #                     WHEN %(today)s::date - act.date_deadline::date < 0 Then 'planned'
#         #                 END AS states
#         #             FROM mail_activity AS act
#         #             JOIN ir_model AS m ON act.res_model_id = m.id
#         #             WHERE user_id = %(user_id)s  and active=True
#         #             GROUP BY m.id, states, act.res_model;
#         #             """
        
#         query = """SELECT m.id, count(*), act.res_model as model, act.res_id,
#                             CASE
#                                 WHEN %(today)s::date - act.date_deadline::date = 0 Then 'today'
#                                 WHEN %(today)s::date - act.date_deadline::date > 0 Then 'overdue'
#                                 WHEN %(today)s::date - act.date_deadline::date < 0 Then 'planned'
#                             END AS states
#                         FROM mail_activity AS act
#                         JOIN ir_model AS m ON act.res_id = m.id
#                         WHERE act.res_model = 'mailing.mailing' AND act.user_id = %(user_id)s  
#                         GROUP BY m.id, states, act.res_model, act.res_id;
#                         """
#         self.env.cr.execute(query, {
#             'today': fields.Date.context_today(self),
#             'user_id': self.env.uid,
#         })
#         activity_data = self.env.cr.dictfetchall()
#         activities_by_record_by_model_name={}
#         for activity in activity_data:
#             record = self.env[activity.res_model].browse(activity.res_id)
#             activities_by_record_by_model_name[activity.res_model][record] += activity
#         model_ids = list({self.env["ir.model"]._get(name).id for name in activities_by_record_by_model_name.keys()})
#         user_activities = {}
#         for model_name, activities_by_record in activities_by_record_by_model_name.items():
#             domain = [("id", "in", list({r.id for r in activities_by_record.keys()}))]
#             allowed_records = self.env[model_name].search(domain)
#             if not allowed_records:
#                 continue
#             module = self.env[model_name]._original_module
#             icon = module and modules.module.get_module_icon(module)
#             model = self.env["ir.model"]._get(model_name).with_prefetch(model_ids)
#             user_activities[model_name] = {
#                 "id": model.id,
#                 "name": model.name,
#                 "model": model_name,
#                 "type": "activity",
#                 "icon": icon,
#                 "total_count": 0,
#                 "today_count": 0,
#                 "overdue_count": 0,
#                 "planned_count": 0,
#                 "actions": [
#                     {
#                         "icon": "fa-clock-o",
#                         "name": "Summary",
#                     }
#                 ],
#             }
#             for record, activities in activities_by_record.items():
#                 if record not in allowed_records:
#                     continue
#                 for activity in activities:
#                     user_activities[model_name]["%s_count" % activity.state] += 1
#                     if activity.state in ("today", "overdue"):
#                         user_activities[model_name]["total_count"] += 1
#         activities = list(user_activities.values())
#         if self.env['ir.module.module'].sudo().search([('name', '=', 'note'), ('state', '=', 'installed')]):
#             notes_count = self.env['note.note'].search_count(
#                 [('user_id', '=', self.env.uid)])
#             if notes_count:
#                 note_index = next((index for (index, a) in enumerate(
#                     activities) if a["model"] == "note.note"), None)
#                 note_label = _('Notes')
#                 if note_index is not None:
#                     activities[note_index]['name'] = note_label
#                 else:
#                     activities.append({
#                         'type': 'activity',
#                         'name': note_label,
#                         'model': 'note.note',
#                         'icon': modules.module.get_module_icon(self.env['note.note']._original_module),
#                         'total_count': 0,
#                         'today_count': 0,
#                         'overdue_count': 0,
#                         'planned_count': 0
#                     })
#         for activity in activities:
#             if self.env['ir.module.module'].sudo().search([('name', '=', 'contacts'), ('state', '=', 'installed')]):
#                 if activity['model'] == 'res.partner':
#                     activity['icon'] = '/sh_activities_management/static/description/contacts_icon.png'
#             if self.env['ir.module.module'].sudo().search([('name', '=', 'mass_mailing'), ('state', '=', 'installed')]):
#                 if activity.get('model') == 'mailing.mailing':
#                     activity['name'] = _('Email Marketing')
#                     break
#             if self.env['ir.module.module'].sudo().search([('name', '=', 'mass_mailing_sms'), ('state', '=', 'installed')]):
#                 if activity.get('model') == 'mailing.mailing':
#                     activities.remove(activity)
#                     query = """SELECT m.mailing_type, count(*), act.res_model as model, act.res_id,
#                                 CASE
#                                     WHEN %(today)s::date - act.date_deadline::date = 0 Then 'today'
#                                     WHEN %(today)s::date - act.date_deadline::date > 0 Then 'overdue'
#                                     WHEN %(today)s::date - act.date_deadline::date < 0 Then 'planned'
#                                 END AS states
#                             FROM mail_activity AS act
#                             JOIN mailing_mailing AS m ON act.res_id = m.id
#                             WHERE act.res_model = 'mailing.mailing' AND act.user_id = %(user_id)s  
#                             GROUP BY m.mailing_type, states, act.res_model, act.res_id;
#                             """
#                     self.env.cr.execute(query, {
#                         'today': fields.Date.context_today(self),
#                         'user_id': self.env.uid,
#                     })
#                     activity_data = self.env.cr.dictfetchall()

#                     user_activities = {}
#                     for act in activity_data:
#                         if not user_activities.get(act['mailing_type']):
#                             if act['mailing_type'] == 'sms':
#                                 module = 'mass_mailing_sms'
#                                 name = _('SMS Marketing')
#                             else:
#                                 module = 'mass_mailing'
#                                 name = _('Email Marketing')
#                             icon = module and modules.module.get_module_icon(
#                                 module)
#                             res_ids = set()
#                             user_activities[act['mailing_type']] = {
#                                 'name': name,
#                                 'model': 'mailing.mailing',
#                                 'type': 'activity',
#                                 'icon': icon,
#                                 'total_count': 0, 'today_count': 0, 'overdue_count': 0, 'planned_count': 0,
#                                 'res_ids': res_ids,
#                             }
#                         user_activities[act['mailing_type']
#                                         ]['res_ids'].add(act['res_id'])
#                         user_activities[act['mailing_type']]['%s_count' %
#                                                              act['states']] += act['count']
#                         if act['states'] in ('today', 'overdue'):
#                             user_activities[act['mailing_type']
#                                             ]['total_count'] += act['count']

#                     for mailing_type in user_activities.keys():
#                         user_activities[mailing_type].update({
#                             'actions': [{'icon': 'fa-clock-o', 'name': 'Summary', }],
#                             'domain': json.dumps([['activity_ids.res_id', 'in', list(user_activities[mailing_type]['res_ids'])]])
#                         })
#                     activities.extend(list(user_activities.values()))
#                     break
#             if self.env['ir.module.module'].sudo().search([('name', '=', 'calendar'), ('state', '=', 'installed')]):
#                 EventModel = self.env['calendar.event']
#                 meetings_lines = EventModel.search_read(
#                     self._systray_get_calendar_event_domain(),
#                     ['id', 'start', 'name', 'allday'],
#                     order='start')
#                 if meetings_lines:
#                     meeting_label = _("Today's Meetings")
#                     meetings_systray = {
#                         'id': self.env['ir.model']._get('calendar.event').id,
#                         'type': 'meeting',
#                         'name': meeting_label,
#                         'model': 'calendar.event',
#                         'icon': modules.module.get_module_icon(EventModel._original_module),
#                         'meetings': meetings_lines,
#                         "view_type": EventModel._systray_view,
#                     }

#                     activities.insert(0, meetings_systray)
#         return activities


class ActivityDashboard(models.Model):
    _name = 'activity.dashboard'
    _description = 'Activity Dashboard'

    @api.model
    def get_document_models(self):
        document_models = False
        uid = request.session.uid
        user = request.env['res.users'].sudo().browse(uid)
        cids = request.httprequest.cookies.get('cids', str(user.company_id.id))
        cids = [int(cid) for cid in cids.split(',')]
        company_id = request.env['res.company'].sudo().browse(cids[0])
        if company_id.sh_document_model:
            if company_id.sh_document_model_ids:
                domain = [('id','in',company_id.sh_document_model_ids.ids)]
                document_models = request.env["ir.model"].sudo().search_read(domain,['id','name'])
        return document_models

    @api.model
    def get_sh_crm_activity_planned_count_tbl(self, filter_date, filter_user, start_date, end_date, filter_supervisor):
        uid = request.session.uid
        user = request.env['res.users'].sudo().browse(uid)
        cids = request.httprequest.cookies.get('cids', str(user.company_id.id))
        cids = [int(cid) for cid in cids.split(',')]
        doman = [
            ('company_id', 'in', cids)
        ]
        crm_days_filter = filter_date
        custom_date_start = start_date
        custom_date_end = end_date
        if crm_days_filter == 'today':
            dt_flt1 = []
            dt_flt1.append('date_deadline')
            dt_flt1.append('>=')
            dt_flt1.append(datetime.now().date().strftime("%Y/%m/%d"))
            doman.append(tuple(dt_flt1))
            dt_flt2 = []
            dt_flt2.append('date_deadline')
            dt_flt2.append('<=')
            dt_flt2.append(datetime.now().date().strftime("%Y/%m/%d"))
            doman.append(tuple(dt_flt2))
        elif crm_days_filter == 'yesterday':
            dt_flt1 = []
            dt_flt1.append('date_deadline')
            dt_flt1.append('>=')
            prev_day = (datetime.now().date() -
                        relativedelta(days=1)).strftime('%Y/%m/%d')
            dt_flt1.append(prev_day)
            doman.append(tuple(dt_flt1))
            dt_flt2 = []
            dt_flt2.append('date_deadline')
            dt_flt2.append('<=')
            prev_day = (datetime.now().date() -
                        relativedelta(days=1)).strftime('%Y/%m/%d')
            dt_flt2.append(prev_day)
            doman.append(tuple(dt_flt2))
        elif crm_days_filter == 'weekly':  # current week
            dt_flt1 = []
            dt_flt1.append('date_deadline')
            dt_flt1.append('>')
            dt_flt1.append(
                (datetime.now().date() - relativedelta(weeks=1, weekday=0)).strftime("%Y/%m/%d"))
            doman.append(tuple(dt_flt1))
            dt_flt2 = []
            dt_flt2.append('date_deadline')
            dt_flt2.append('<=')
            dt_flt2.append(datetime.now().date().strftime("%Y/%m/%d"))
            doman.append(tuple(dt_flt2))
        elif crm_days_filter == 'prev_week':  # Previous week
            dt_flt1 = []
            dt_flt1.append('date_deadline')
            dt_flt1.append('>')
            dt_flt1.append(
                (datetime.now().date() - relativedelta(weeks=2, weekday=0)).strftime("%Y/%m/%d"))
            doman.append(tuple(dt_flt1))
            dt_flt2 = []
            dt_flt2.append('date_deadline')
            dt_flt2.append('<=')
            dt_flt2.append(
                (datetime.now().date() - relativedelta(weeks=1, weekday=6)).strftime("%Y/%m/%d"))
            doman.append(tuple(dt_flt2))
        elif crm_days_filter == 'monthly':  # Current Month
            dt_flt1 = []
            dt_flt1.append('date_deadline')
            dt_flt1.append('>')
            dt_flt1.append((datetime.now().date()).strftime("%Y/%m/01"))
            doman.append(tuple(dt_flt1))
            dt_flt2 = []
            dt_flt2.append('date_deadline')
            dt_flt2.append('<=')
            dt_flt2.append(datetime.now().date().strftime("%Y/%m/%d"))
            doman.append(tuple(dt_flt2))
        elif crm_days_filter == 'prev_month':  # Previous Month
            dt_flt1 = []
            dt_flt1.append('date_deadline')
            dt_flt1.append('>')
            dt_flt1.append(
                (datetime.now().date() - relativedelta(months=1)).strftime("%Y/%m/01"))
            doman.append(tuple(dt_flt1))
            dt_flt2 = []
            dt_flt2.append('date_deadline')
            dt_flt2.append('<')
            dt_flt2.append(datetime.now().date().strftime("%Y/%m/01"))
            doman.append(tuple(dt_flt2))
        elif crm_days_filter == 'cur_year':  # Current Year
            dt_flt1 = []
            dt_flt1.append('date_deadline')
            dt_flt1.append('>')
            dt_flt1.append((datetime.now().date()).strftime("%Y/01/01"))
            doman.append(tuple(dt_flt1))
            dt_flt2 = []
            dt_flt2.append('date_deadline')
            dt_flt2.append('<=')
            dt_flt2.append(datetime.now().date().strftime("%Y/%m/%d"))
            doman.append(tuple(dt_flt2))
        elif crm_days_filter == 'prev_year':  # Previous Year
            dt_flt1 = []
            dt_flt1.append('date_deadline')
            dt_flt1.append('>')
            dt_flt1.append(
                (datetime.now().date() - relativedelta(years=1)).strftime("%Y/01/01"))
            doman.append(tuple(dt_flt1))
            dt_flt2 = []
            dt_flt2.append('date_deadline')
            dt_flt2.append('<')
            dt_flt2.append(datetime.now().date().strftime("%Y/01/01"))
            doman.append(tuple(dt_flt2))
        elif crm_days_filter == 'custom':
            if custom_date_start and custom_date_end:
                dt_flt1 = []
                dt_flt1.append('date_deadline')
                dt_flt1.append('>')
                dt_flt1.append(datetime.strptime(
                    str(custom_date_start), DEFAULT_SERVER_DATE_FORMAT).strftime("%Y/%m/%d"))
                doman.append(tuple(dt_flt1))
                dt_flt2 = []
                dt_flt2.append('date_deadline')
                dt_flt2.append('<=')
                dt_flt2.append(datetime.strptime(
                    str(custom_date_end), DEFAULT_SERVER_DATE_FORMAT).strftime("%Y/%m/%d"))
                doman.append(tuple(dt_flt2))
        # FILTER USER
        if filter_user not in ['', "", None, False]:
            doman.append(('|'))
            doman.append(('sh_user_ids', 'in', [int(filter_user)]))
            doman.append(('user_id', '=', int(filter_user)))
        else:
            if self.env.user.has_group('sh_activities_management_basic.group_activity_supervisor') and self.env.user.has_group('sh_activities_management_basic.group_activity_user') and not self.env.user.has_group('sh_activities_management_basic.group_activity_manager'):
                doman.append(('|'))
                doman.append(('|'))
                doman.append(('user_id', '!=', self.env.user.id))
                doman.append(('user_id', '=', self.env.user.id))
                doman.append(('sh_user_ids', 'in', [self.env.user.id]))

            elif not self.env.user.has_group('sh_activities_management_basic.group_activity_supervisor') and self.env.user.has_group('sh_activities_management_basic.group_activity_user') and not self.env.user.has_group('sh_activities_management_basic.group_activity_manager'):
                doman.append(('|'))
                doman.append(('sh_user_ids', 'in', [self.env.user.id]))
                doman.append(('user_id', '=', self.env.user.id))
        if filter_supervisor not in ['', "", None, False]:
            doman.append(('supervisor_id', '=', int(filter_supervisor)))
        else:
            if self.env.user.has_group('sh_activities_management_basic.group_activity_supervisor') and self.env.user.has_group('sh_activities_management_basic.group_activity_user') and not self.env.user.has_group('sh_activities_management_basic.group_activity_manager'):
                doman.append(('|'))
                doman.append(('|'))
                doman.append(('supervisor_id', '=', self.env.user.id))
                doman.append(('sh_user_ids', 'in', [self.env.user.id]))
                doman.append(('user_id', '=', self.env.user.id))
            elif not self.env.user.has_group('sh_activities_management_basic.group_activity_supervisor') and self.env.user.has_group('sh_activities_management_basic.group_activity_user') and not self.env.user.has_group('sh_activities_management_basic.group_activity_manager'):
                doman.append(('|'))
                doman.append(('|'))
                doman.append(('supervisor_id', '=', self.env.user.id))
                doman.append(('supervisor_id', '!=', self.env.user.id))
                doman.append(('supervisor_id', '=', False))
        doman.append(('|'))
        doman.append(('active', '=', True))
        doman.append(('active', '=', False))
        
        # -------------------------------------
        # ALL ACTIVITES
        # -------------------------------------

        from_clause, where_clause_all_activities, where_params_all_activities = self.env['mail.activity']._where_calc(doman).get_sql()

        query = f'''
            SELECT "mail_activity".id FROM "mail_activity" WHERE {where_clause_all_activities}
        '''

        self.env.cr.execute(query, where_params_all_activities)    
        result_all = self._cr.fetchall()

        all_activities_ids = [r[0] for r in result_all]
        activities = self.env['mail.activity'].browse(all_activities_ids)
        
        # -------------------------------------
        # ALL ACTIVITES
        # -------------------------------------

        # return {}

        # -------------------------------------
        # PLANNED ACTIVITES
        # -------------------------------------

        # planned_doman = doman.copy()
        planned_doman = expression.AND([doman.copy(), [('active','=',True)]])
        planned_doman = expression.AND([doman.copy(), [('date_deadline','!=',False)]])
        planned_doman = expression.AND([doman.copy(), [('date_deadline','>=',fields.Date.today())]])
             
        from_clause, where_clause_planned_activities, where_params_planned_activities = self.env['mail.activity']._where_calc(planned_doman).get_sql()

        query = f'''
            SELECT "mail_activity".id FROM "mail_activity" WHERE {where_clause_planned_activities}
        '''

        self.env.cr.execute(query, where_params_planned_activities)    
        result_planned_activities = self._cr.fetchall()

        planned_activities_list = [r[0] for r in result_planned_activities]
        planned_activities = self.env['mail.activity'].browse(planned_activities_list)
        
        # -------------------------------------
        # PLANNED ACTIVITES
        # -------------------------------------

        # -------------------------------------
        # OVERDUE ACTIVITES
        # -------------------------------------
          
        # overdue_doman = doman.copy()
        overdue_doman = expression.AND([doman.copy(), [('active','=',True)]])
        overdue_doman = expression.AND([doman.copy(), [('date_deadline','!=',False)]])
        overdue_doman = expression.AND([doman.copy(), [('date_deadline','<',fields.Date.today())]])

        from_clause, where_clause_overdue_activities, where_params_overdue_activities = self.env['mail.activity']._where_calc(overdue_doman).get_sql()

        query = f'''
            SELECT "mail_activity".id FROM "mail_activity" WHERE {where_clause_overdue_activities}
        '''

        self.env.cr.execute(query, where_params_overdue_activities)    
        result_overdue_activities = self._cr.fetchall()

        
        overdue_activities_list = [r[0] for r in result_overdue_activities]
        overdue_activities = self.env['mail.activity'].browse(overdue_activities_list)

        # -------------------------------------
        # OVERDUE ACTIVITES
        # -------------------------------------

        # -------------------------------------
        # COMPLETED ACTIVITES
        # ------------------------------------- 
        
        # completed_doman = doman.copy()
        completed_doman = expression.AND([doman.copy(), [('active','=',True)]])
        completed_doman = expression.AND([doman.copy(), [('state','=','done')]])

        from_clause, where_clause_completed_activities, where_params_completed_activities = self.env['mail.activity']._where_calc(completed_doman).get_sql()

        query = f'''
            SELECT "mail_activity".id FROM "mail_activity" WHERE {where_clause_completed_activities}
        '''

        self.env.cr.execute(query, where_params_completed_activities)    
        result_completed_activities = self._cr.fetchall()

        completed_activities_list = [r[0] for r in result_completed_activities]
        completed_activities = self.env['mail.activity'].browse(completed_activities_list)
        
        # -------------------------------------
        # COMPLETED ACTIVITES
        # ------------------------------------- 

        # -------------------------------------
        # CANCELLED ACTIVITES
        # -------------------------------------


        # cancelled_doman = doman.copy()
        cancelled_doman = expression.AND([doman.copy(), [('active','=',False)]])
        cancelled_doman = expression.AND([doman.copy(), [('state','=','cancel')]])

        from_clause, where_clause_cancelled_activities, where_params_cancelled_activities = self.env['mail.activity']._where_calc(cancelled_doman).get_sql()

        query = f'''
            SELECT "mail_activity".id FROM "mail_activity" WHERE {where_clause_cancelled_activities}
        '''

        self.env.cr.execute(query, where_params_cancelled_activities)    
        result_cancelled_activities = self._cr.fetchall()
        
        cancelled_activities_list = [r[0] for r in result_cancelled_activities]
        cancelled_activities = self.env['mail.activity'].browse(cancelled_activities_list)
        

        # -------------------------------------
        # CANCELLED ACTIVITES
        # -------------------------------------
        return self.env['ir.ui.view'].with_context()._render_template('sh_activities_management_basic.sh_crm_db_activity_count_box', {
            'planned_activities': planned_activities_list,
            'overdue_activities': overdue_activities_list,
            'all_activities': all_activities_ids,
            'completed_activities': completed_activities_list,
            'planned_acitvities_count': len(planned_activities),
            'overdue_activities_count': len(overdue_activities),
            'completed_activities_count': len(completed_activities),
            'cancelled_activities_count': len(cancelled_activities),
            'cancelled_activities': cancelled_activities_list,
            'all_activities_count': len(activities.ids),
        })

    @api.model
    def get_sh_crm_activity_todo_tbl(self, filter_date, filter_user, start_date, end_date, filter_supervisor, current_page):
        uid = request.session.uid
        user = request.env['res.users'].sudo().browse(uid)
        cids = request.httprequest.cookies.get('cids', str(user.company_id.id))
        cids = [int(cid) for cid in cids.split(',')]
        doman = [
            ('company_id', 'in', cids),
            ('active', '=', True),
            ('date_deadline', '>=', fields.Date.today())
        ]
        crm_days_filter = filter_date
        custom_date_start = start_date
        custom_date_end = end_date
        if crm_days_filter == 'today':
            dt_flt1 = []
            dt_flt1.append('date_deadline')
            dt_flt1.append('>=')
            dt_flt1.append(datetime.now().date().strftime("%Y/%m/%d"))
            doman.append(tuple(dt_flt1))
            dt_flt2 = []
            dt_flt2.append('date_deadline')
            dt_flt2.append('<=')
            dt_flt2.append(datetime.now().date().strftime("%Y/%m/%d"))
            doman.append(tuple(dt_flt2))
        elif crm_days_filter == 'yesterday':
            dt_flt1 = []
            dt_flt1.append('date_deadline')
            dt_flt1.append('>=')
            prev_day = (datetime.now().date() -
                        relativedelta(days=1)).strftime('%Y/%m/%d')
            dt_flt1.append(prev_day)
            doman.append(tuple(dt_flt1))
            dt_flt2 = []
            dt_flt2.append('date_deadline')
            dt_flt2.append('<=')
            prev_day = (datetime.now().date() -
                        relativedelta(days=1)).strftime('%Y/%m/%d')
            dt_flt2.append(prev_day)
            doman.append(tuple(dt_flt2))
        elif crm_days_filter == 'weekly':  # current week
            dt_flt1 = []
            dt_flt1.append('date_deadline')
            dt_flt1.append('>')
            dt_flt1.append(
                (datetime.now().date() - relativedelta(weeks=1, weekday=0)).strftime("%Y/%m/%d"))
            doman.append(tuple(dt_flt1))
            dt_flt2 = []
            dt_flt2.append('date_deadline')
            dt_flt2.append('<=')
            dt_flt2.append(datetime.now().date().strftime("%Y/%m/%d"))
            doman.append(tuple(dt_flt2))
        elif crm_days_filter == 'prev_week':  # Previous week
            dt_flt1 = []
            dt_flt1.append('date_deadline')
            dt_flt1.append('>')
            dt_flt1.append(
                (datetime.now().date() - relativedelta(weeks=2, weekday=0)).strftime("%Y/%m/%d"))
            doman.append(tuple(dt_flt1))
            dt_flt2 = []
            dt_flt2.append('date_deadline')
            dt_flt2.append('<=')
            dt_flt2.append(
                (datetime.now().date() - relativedelta(weeks=1, weekday=6)).strftime("%Y/%m/%d"))
            doman.append(tuple(dt_flt2))
        elif crm_days_filter == 'monthly':  # Current Month
            dt_flt1 = []
            dt_flt1.append('date_deadline')
            dt_flt1.append('>')
            dt_flt1.append((datetime.now().date()).strftime("%Y/%m/01"))
            doman.append(tuple(dt_flt1))
            dt_flt2 = []
            dt_flt2.append('date_deadline')
            dt_flt2.append('<=')
            dt_flt2.append(datetime.now().date().strftime("%Y/%m/%d"))
            doman.append(tuple(dt_flt2))
        elif crm_days_filter == 'prev_month':  # Previous Month
            dt_flt1 = []
            dt_flt1.append('date_deadline')
            dt_flt1.append('>')
            dt_flt1.append(
                (datetime.now().date() - relativedelta(months=1)).strftime("%Y/%m/01"))
            doman.append(tuple(dt_flt1))
            dt_flt2 = []
            dt_flt2.append('date_deadline')
            dt_flt2.append('<')
            dt_flt2.append(datetime.now().date().strftime("%Y/%m/01"))
            doman.append(tuple(dt_flt2))
        elif crm_days_filter == 'cur_year':  # Current Year
            dt_flt1 = []
            dt_flt1.append('date_deadline')
            dt_flt1.append('>')
            dt_flt1.append((datetime.now().date()).strftime("%Y/01/01"))
            doman.append(tuple(dt_flt1))
            dt_flt2 = []
            dt_flt2.append('date_deadline')
            dt_flt2.append('<=')
            dt_flt2.append(datetime.now().date().strftime("%Y/%m/%d"))
            doman.append(tuple(dt_flt2))
        elif crm_days_filter == 'prev_year':  # Previous Year
            dt_flt1 = []
            dt_flt1.append('date_deadline')
            dt_flt1.append('>')
            dt_flt1.append(
                (datetime.now().date() - relativedelta(years=1)).strftime("%Y/01/01"))
            doman.append(tuple(dt_flt1))
            dt_flt2 = []
            dt_flt2.append('date_deadline')
            dt_flt2.append('<')
            dt_flt2.append(datetime.now().date().strftime("%Y/01/01"))
            doman.append(tuple(dt_flt2))
        elif crm_days_filter == 'custom':
            if custom_date_start and custom_date_end:
                dt_flt1 = []
                dt_flt1.append('date_deadline')
                dt_flt1.append('>')
                dt_flt1.append(datetime.strptime(
                    str(custom_date_start), DEFAULT_SERVER_DATE_FORMAT).strftime("%Y/%m/%d"))
                doman.append(tuple(dt_flt1))
                dt_flt2 = []
                dt_flt2.append('date_deadline')
                dt_flt2.append('<=')
                dt_flt2.append(datetime.strptime(
                    str(custom_date_end), DEFAULT_SERVER_DATE_FORMAT).strftime("%Y/%m/%d"))
                doman.append(tuple(dt_flt2))
        # FILTER USER
        if filter_user not in ['', "", None, False]:
            doman.append(('|'))
            doman.append(('sh_user_ids', 'in', [int(filter_user)]))
            doman.append(('user_id', '=', int(filter_user)))
        else:
            if self.env.user.has_group('sh_activities_management_basic.group_activity_supervisor') and self.env.user.has_group('sh_activities_management_basic.group_activity_user') and not self.env.user.has_group('sh_activities_management_basic.group_activity_manager'):
                doman.append(('|'))
                doman.append(('|'))
                doman.append(('user_id', '!=', self.env.user.id))
                doman.append(('user_id', '=', self.env.user.id))
                doman.append(('sh_user_ids', 'in', [self.env.user.id]))
            elif not self.env.user.has_group('sh_activities_management_basic.group_activity_supervisor') and self.env.user.has_group('sh_activities_management_basic.group_activity_user') and not self.env.user.has_group('sh_activities_management_basic.group_activity_manager'):
                doman.append(('|'))
                doman.append(('sh_user_ids', 'in', [self.env.user.id]))
                doman.append(('user_id', '=', self.env.user.id))
        if filter_supervisor not in ['', "", None, False]:
            doman.append(('supervisor_id', '=', int(filter_supervisor)))
        else:
            if self.env.user.has_group('sh_activities_management_basic.group_activity_supervisor') and self.env.user.has_group('sh_activities_management_basic.group_activity_user') and not self.env.user.has_group('sh_activities_management_basic.group_activity_manager'):
                doman.append(('|'))
                doman.append(('|'))
                doman.append(('supervisor_id', '=', self.env.user.id))
                doman.append(('sh_user_ids', 'in', [self.env.user.id]))
                doman.append(('user_id', '=', self.env.user.id))
            elif not self.env.user.has_group('sh_activities_management_basic.group_activity_supervisor') and self.env.user.has_group('sh_activities_management_basic.group_activity_user') and not self.env.user.has_group('sh_activities_management_basic.group_activity_manager'):
                doman.append(('|'))
                doman.append(('|'))
                doman.append(('supervisor_id', '=', self.env.user.id))
                doman.append(('supervisor_id', '!=', self.env.user.id))
                doman.append(('supervisor_id', '=', False))
        # -------------------------------------
        # ALL ACTIVITES
        # -------------------------------------

        from_clause, where_clause_all_activities, where_params_all_activities = self.env['mail.activity']._where_calc(doman).get_sql()

        query = f'''
            SELECT "mail_activity".id FROM "mail_activity" WHERE {where_clause_all_activities}
        '''

        self.env.cr.execute(query, where_params_all_activities)    
        result_all = self._cr.fetchall()

        all_activities_ids = [r[0] for r in result_all]
        activities = self.env['mail.activity'].browse(all_activities_ids)

        # return {}

        # -------------------------------------
        # PLANNED ACTIVITES
        # -------------------------------------

        total_pages = 0.0
        total_planned_activities = len(all_activities_ids)
        record_limit = self.env.company.sh_planned_table
        if total_planned_activities > 0 and record_limit > 0:
            total_pages = math.ceil(
                float(total_planned_activities) / float(record_limit))
        current_page = int(current_page)
        start = self.env.company.sh_planned_table * (current_page-1)
        stop = current_page * self.env.company.sh_planned_table
        activities = activities[start:stop]
        return self.env['ir.ui.view'].with_context()._render_template('sh_activities_management_basic.sh_crm_db_activity_todo_tbl', {
            'activities': activities,
            'planned_acitvities_count': total_planned_activities,
            'total_pages': total_pages,
            'current_page': current_page,
        })

    @api.model
    def get_sh_crm_activity_all_tbl(self, filter_date, filter_user, start_date, end_date, filter_supervisor, current_page):
        uid = request.session.uid
        user = request.env['res.users'].sudo().browse(uid)
        cids = request.httprequest.cookies.get('cids', str(user.company_id.id))
        cids = [int(cid) for cid in cids.split(',')]
        doman = [('company_id', 'in', cids)]
        crm_days_filter = filter_date
        custom_date_start = start_date
        custom_date_end = end_date
        if crm_days_filter == 'today':
            dt_flt1 = []
            dt_flt1.append('date_deadline')
            dt_flt1.append('>=')
            dt_flt1.append(datetime.now().date().strftime("%Y/%m/%d"))
            doman.append(tuple(dt_flt1))

            dt_flt2 = []
            dt_flt2.append('date_deadline')
            dt_flt2.append('<=')
            dt_flt2.append(datetime.now().date().strftime("%Y/%m/%d"))
            doman.append(tuple(dt_flt2))
        elif crm_days_filter == 'yesterday':
            dt_flt1 = []
            dt_flt1.append('date_deadline')
            dt_flt1.append('>=')
            prev_day = (datetime.now().date() -
                        relativedelta(days=1)).strftime('%Y/%m/%d')
            dt_flt1.append(prev_day)
            doman.append(tuple(dt_flt1))
            dt_flt2 = []
            dt_flt2.append('date_deadline')
            dt_flt2.append('<=')
            prev_day = (datetime.now().date() -
                        relativedelta(days=1)).strftime('%Y/%m/%d')
            dt_flt2.append(prev_day)
            doman.append(tuple(dt_flt2))
        elif crm_days_filter == 'weekly':  # current week
            dt_flt1 = []
            dt_flt1.append('date_deadline')
            dt_flt1.append('>')
            dt_flt1.append(
                (datetime.now().date() - relativedelta(weeks=1, weekday=0)).strftime("%Y/%m/%d"))
            doman.append(tuple(dt_flt1))
            dt_flt2 = []
            dt_flt2.append('date_deadline')
            dt_flt2.append('<=')
            dt_flt2.append(datetime.now().date().strftime("%Y/%m/%d"))
            doman.append(tuple(dt_flt2))
        elif crm_days_filter == 'prev_week':  # Previous week
            dt_flt1 = []
            dt_flt1.append('date_deadline')
            dt_flt1.append('>')
            dt_flt1.append(
                (datetime.now().date() - relativedelta(weeks=2, weekday=0)).strftime("%Y/%m/%d"))
            doman.append(tuple(dt_flt1))
            dt_flt2 = []
            dt_flt2.append('date_deadline')
            dt_flt2.append('<=')
            dt_flt2.append(
                (datetime.now().date() - relativedelta(weeks=1, weekday=6)).strftime("%Y/%m/%d"))
            doman.append(tuple(dt_flt2))
        elif crm_days_filter == 'monthly':  # Current Month
            dt_flt1 = []
            dt_flt1.append('date_deadline')
            dt_flt1.append('>')
            dt_flt1.append((datetime.now().date()).strftime("%Y/%m/01"))
            doman.append(tuple(dt_flt1))
            dt_flt2 = []
            dt_flt2.append('date_deadline')
            dt_flt2.append('<=')
            dt_flt2.append(datetime.now().date().strftime("%Y/%m/%d"))
            doman.append(tuple(dt_flt2))
        elif crm_days_filter == 'prev_month':  # Previous Month
            dt_flt1 = []
            dt_flt1.append('date_deadline')
            dt_flt1.append('>')
            dt_flt1.append(
                (datetime.now().date() - relativedelta(months=1)).strftime("%Y/%m/01"))
            doman.append(tuple(dt_flt1))
            dt_flt2 = []
            dt_flt2.append('date_deadline')
            dt_flt2.append('<')
            dt_flt2.append(datetime.now().date().strftime("%Y/%m/01"))
            doman.append(tuple(dt_flt2))
        elif crm_days_filter == 'cur_year':  # Current Year
            dt_flt1 = []
            dt_flt1.append('date_deadline')
            dt_flt1.append('>')
            dt_flt1.append((datetime.now().date()).strftime("%Y/01/01"))
            doman.append(tuple(dt_flt1))
            dt_flt2 = []
            dt_flt2.append('date_deadline')
            dt_flt2.append('<=')
            dt_flt2.append(datetime.now().date().strftime("%Y/%m/%d"))
            doman.append(tuple(dt_flt2))
        elif crm_days_filter == 'prev_year':  # Previous Year
            dt_flt1 = []
            dt_flt1.append('date_deadline')
            dt_flt1.append('>')
            dt_flt1.append(
                (datetime.now().date() - relativedelta(years=1)).strftime("%Y/01/01"))
            doman.append(tuple(dt_flt1))
            dt_flt2 = []
            dt_flt2.append('date_deadline')
            dt_flt2.append('<')
            dt_flt2.append(datetime.now().date().strftime("%Y/01/01"))
            doman.append(tuple(dt_flt2))
        elif crm_days_filter == 'custom':
            if custom_date_start and custom_date_end:
                dt_flt1 = []
                dt_flt1.append('date_deadline')
                dt_flt1.append('>')
                dt_flt1.append(datetime.strptime(
                    str(custom_date_start), DEFAULT_SERVER_DATE_FORMAT).strftime("%Y/%m/%d"))
                doman.append(tuple(dt_flt1))
                dt_flt2 = []
                dt_flt2.append('date_deadline')
                dt_flt2.append('<=')
                dt_flt2.append(datetime.strptime(
                    str(custom_date_end), DEFAULT_SERVER_DATE_FORMAT).strftime("%Y/%m/%d"))
                doman.append(tuple(dt_flt2))
        # FILTER USER
        if filter_user not in ['', "", None, False]:
            doman.append(('|'))
            doman.append(('sh_user_ids', 'in', [int(filter_user)]))
            doman.append(('user_id', '=', int(filter_user)))
        else:
            if self.env.user.has_group('sh_activities_management_basic.group_activity_supervisor') and self.env.user.has_group('sh_activities_management_basic.group_activity_user') and not self.env.user.has_group('sh_activities_management_basic.group_activity_manager'):
                doman.append(('|'))
                doman.append(('|'))
                doman.append(('user_id', '!=', self.env.user.id))
                doman.append(('user_id', '=', self.env.user.id))
                doman.append(('sh_user_ids', 'in', [self.env.user.id]))

            elif not self.env.user.has_group('sh_activities_management_basic.group_activity_supervisor') and self.env.user.has_group('sh_activities_management_basic.group_activity_user') and not self.env.user.has_group('sh_activities_management_basic.group_activity_manager'):
                doman.append(('|'))
                doman.append(('user_id', '=', self.env.user.id))
                doman.append(('sh_user_ids', 'in', [self.env.user.id]))
        if filter_supervisor not in ['', "", None, False]:
            doman.append(('supervisor_id', '=', int(filter_supervisor)))
        else:
            if self.env.user.has_group('sh_activities_management_basic.group_activity_supervisor') and self.env.user.has_group('sh_activities_management_basic.group_activity_user') and not self.env.user.has_group('sh_activities_management_basic.group_activity_manager'):
                doman.append(('|'))
                doman.append(('|'))
                doman.append(('supervisor_id', '=', self.env.user.id))
                doman.append(('sh_user_ids', 'in', [self.env.user.id]))
                doman.append(('user_id', '=', self.env.user.id))
            elif not self.env.user.has_group('sh_activities_management_basic.group_activity_supervisor') and self.env.user.has_group('sh_activities_management_basic.group_activity_user') and not self.env.user.has_group('sh_activities_management_basic.group_activity_manager'):
                doman.append(('|'))
                doman.append(('|'))
                doman.append(('supervisor_id', '=', self.env.user.id))
                doman.append(('supervisor_id', '!=', self.env.user.id))
                doman.append(('supervisor_id', '=', False))
        doman.append(('|'))
        doman.append(('active', '=', True))
        doman.append(('active', '=', False))
        
        # -------------------------------------
        # ALL ACTIVITES
        # -------------------------------------

        from_clause, where_clause_all_activities, where_params_all_activities = self.env['mail.activity']._where_calc(doman).get_sql()

        query = f'''
            SELECT "mail_activity".id FROM "mail_activity" WHERE {where_clause_all_activities}
        '''

        self.env.cr.execute(query, where_params_all_activities)    
        result_all = self._cr.fetchall()

        all_activities_ids = [r[0] for r in result_all]
        activities = self.env['mail.activity'].browse(all_activities_ids)

        # return {}

        # -------------------------------------
        # ALL ACTIVITES
        # -------------------------------------

        total_pages = 0.0
        total_activities = len(all_activities_ids)
        record_limit = self.env.company.sh_planned_table
        if total_activities > 0 and record_limit > 0:
            total_pages = math.ceil(
                float(total_activities) / float(record_limit))
        current_page = int(current_page)
        start = self.env.company.sh_all_table * (current_page-1)
        stop = current_page * self.env.company.sh_all_table
        activities = activities[start:stop]
        return self.env['ir.ui.view'].with_context()._render_template('sh_activities_management_basic.sh_crm_db_activity_all_tbl', {
            'activities': activities,
            'all_acitvities_count': total_activities,
            'total_pages': total_pages,
            'current_page': current_page,
        })

    @api.model
    def get_sh_crm_activity_completed_tbl(self, filter_date, filter_user, start_date, end_date, filter_supervisor, current_page):
        uid = request.session.uid
        user = request.env['res.users'].sudo().browse(uid)
        cids = request.httprequest.cookies.get('cids', str(user.company_id.id))
        cids = [int(cid) for cid in cids.split(',')]
        doman = [('company_id', 'in', cids),
                 ('active', '=', False), ('state', '=', 'done')]
        crm_days_filter = filter_date
        custom_date_start = start_date
        custom_date_end = end_date
        if crm_days_filter == 'today':
            dt_flt1 = []
            dt_flt1.append('date_deadline')
            dt_flt1.append('>=')
            dt_flt1.append(datetime.now().date().strftime("%Y/%m/%d"))
            doman.append(tuple(dt_flt1))
            dt_flt2 = []
            dt_flt2.append('date_deadline')
            dt_flt2.append('<=')
            dt_flt2.append(datetime.now().date().strftime("%Y/%m/%d"))
            doman.append(tuple(dt_flt2))
        elif crm_days_filter == 'yesterday':
            dt_flt1 = []
            dt_flt1.append('date_deadline')
            dt_flt1.append('>=')
            prev_day = (datetime.now().date() -
                        relativedelta(days=1)).strftime('%Y/%m/%d')
            dt_flt1.append(prev_day)
            doman.append(tuple(dt_flt1))
            dt_flt2 = []
            dt_flt2.append('date_deadline')
            dt_flt2.append('<=')
            prev_day = (datetime.now().date() -
                        relativedelta(days=1)).strftime('%Y/%m/%d')
            dt_flt2.append(prev_day)
            doman.append(tuple(dt_flt2))
        elif crm_days_filter == 'weekly':  # current week
            dt_flt1 = []
            dt_flt1.append('date_deadline')
            dt_flt1.append('>')
            dt_flt1.append(
                (datetime.now().date() - relativedelta(weeks=1, weekday=0)).strftime("%Y/%m/%d"))
            doman.append(tuple(dt_flt1))
            dt_flt2 = []
            dt_flt2.append('date_deadline')
            dt_flt2.append('<=')
            dt_flt2.append(datetime.now().date().strftime("%Y/%m/%d"))
            doman.append(tuple(dt_flt2))
        elif crm_days_filter == 'prev_week':  # Previous week
            dt_flt1 = []
            dt_flt1.append('date_deadline')
            dt_flt1.append('>')
            dt_flt1.append(
                (datetime.now().date() - relativedelta(weeks=2, weekday=0)).strftime("%Y/%m/%d"))
            doman.append(tuple(dt_flt1))
            dt_flt2 = []
            dt_flt2.append('date_deadline')
            dt_flt2.append('<=')
            dt_flt2.append(
                (datetime.now().date() - relativedelta(weeks=1, weekday=6)).strftime("%Y/%m/%d"))
            doman.append(tuple(dt_flt2))
        elif crm_days_filter == 'monthly':  # Current Month
            dt_flt1 = []
            dt_flt1.append('date_deadline')
            dt_flt1.append('>')
            dt_flt1.append((datetime.now().date()).strftime("%Y/%m/01"))
            doman.append(tuple(dt_flt1))
            dt_flt2 = []
            dt_flt2.append('date_deadline')
            dt_flt2.append('<=')
            dt_flt2.append(datetime.now().date().strftime("%Y/%m/%d"))
            doman.append(tuple(dt_flt2))
        elif crm_days_filter == 'prev_month':  # Previous Month
            dt_flt1 = []
            dt_flt1.append('date_deadline')
            dt_flt1.append('>')
            dt_flt1.append(
                (datetime.now().date() - relativedelta(months=1)).strftime("%Y/%m/01"))
            doman.append(tuple(dt_flt1))
            dt_flt2 = []
            dt_flt2.append('date_deadline')
            dt_flt2.append('<')
            dt_flt2.append(datetime.now().date().strftime("%Y/%m/01"))
            doman.append(tuple(dt_flt2))
        elif crm_days_filter == 'cur_year':  # Current Year
            dt_flt1 = []
            dt_flt1.append('date_deadline')
            dt_flt1.append('>')
            dt_flt1.append((datetime.now().date()).strftime("%Y/01/01"))
            doman.append(tuple(dt_flt1))
            dt_flt2 = []
            dt_flt2.append('date_deadline')
            dt_flt2.append('<=')
            dt_flt2.append(datetime.now().date().strftime("%Y/%m/%d"))
            doman.append(tuple(dt_flt2))
        elif crm_days_filter == 'prev_year':  # Previous Year
            dt_flt1 = []
            dt_flt1.append('date_deadline')
            dt_flt1.append('>')
            dt_flt1.append(
                (datetime.now().date() - relativedelta(years=1)).strftime("%Y/01/01"))
            doman.append(tuple(dt_flt1))
            dt_flt2 = []
            dt_flt2.append('date_deadline')
            dt_flt2.append('<')
            dt_flt2.append(datetime.now().date().strftime("%Y/01/01"))
            doman.append(tuple(dt_flt2))
        elif crm_days_filter == 'custom':
            if custom_date_start and custom_date_end:
                dt_flt1 = []
                dt_flt1.append('date_deadline')
                dt_flt1.append('>')
                dt_flt1.append(datetime.strptime(
                    str(custom_date_start), DEFAULT_SERVER_DATE_FORMAT).strftime("%Y/%m/%d"))
                doman.append(tuple(dt_flt1))
                dt_flt2 = []
                dt_flt2.append('date_deadline')
                dt_flt2.append('<=')
                dt_flt2.append(datetime.strptime(
                    str(custom_date_end), DEFAULT_SERVER_DATE_FORMAT).strftime("%Y/%m/%d"))
                doman.append(tuple(dt_flt2))
        # FILTER USER
        if filter_user not in ['', "", None, False]:
            doman.append(('|'))
            doman.append(('user_id', '=', int(filter_user)))
            doman.append(('sh_user_ids', 'in', [int(filter_user)]))
        else:
            if self.env.user.has_group('sh_activities_management_basic.group_activity_supervisor') and self.env.user.has_group('sh_activities_management_basic.group_activity_user') and not self.env.user.has_group('sh_activities_management_basic.group_activity_manager'):
                doman.append(('|'))
                doman.append(('|'))
                doman.append(('user_id', '!=', self.env.user.id))
                doman.append(('user_id', '=', self.env.user.id))
                doman.append(('sh_user_ids', 'in', [self.env.user.id]))
            elif not self.env.user.has_group('sh_activities_management_basic.group_activity_supervisor') and self.env.user.has_group('sh_activities_management_basic.group_activity_user') and not self.env.user.has_group('sh_activities_management_basic.group_activity_manager'):
                doman.append(('|'))
                doman.append(('user_id', '=', self.env.user.id))
                doman.append(('sh_user_ids', 'in', [self.env.user.id]))
        if filter_supervisor not in ['', "", None, False]:
            doman.append(('supervisor_id', '=', int(filter_supervisor)))
        else:
            if self.env.user.has_group('sh_activities_management_basic.group_activity_supervisor') and self.env.user.has_group('sh_activities_management_basic.group_activity_user') and not self.env.user.has_group('sh_activities_management_basic.group_activity_manager'):
                doman.append(('|'))
                doman.append(('|'))
                doman.append(('supervisor_id', '=', self.env.user.id))
                doman.append(('sh_user_ids', 'in', [self.env.user.id]))
                doman.append(('user_id', '=', self.env.user.id))
            elif not self.env.user.has_group('sh_activities_management_basic.group_activity_supervisor') and self.env.user.has_group('sh_activities_management_basic.group_activity_user') and not self.env.user.has_group('sh_activities_management_basic.group_activity_manager'):
                doman.append(('|'))
                doman.append(('|'))
                doman.append(('supervisor_id', '=', self.env.user.id))
                doman.append(('supervisor_id', '!=', self.env.user.id))
                doman.append(('supervisor_id', '=', False))
        
        # -------------------------------------
        # ALL ACTIVITES
        # -------------------------------------

        from_clause, where_clause_all_activities, where_params_all_activities = self.env['mail.activity']._where_calc(doman).get_sql()

        query = f'''
            SELECT "mail_activity".id FROM "mail_activity" WHERE {where_clause_all_activities}
        '''

        self.env.cr.execute(query, where_params_all_activities)    
        result_all = self._cr.fetchall()

        all_activities_ids = [r[0] for r in result_all]
        activities = self.env['mail.activity'].browse(all_activities_ids)

        # return {}

        # -------------------------------------
        # ALL ACTIVITES
        # -------------------------------------

        total_pages = 0.0
        total_completed_activities = len(all_activities_ids)
        record_limit = self.env.company.sh_planned_table
        if total_completed_activities > 0 and record_limit > 0:
            total_pages = math.ceil(
                float(total_completed_activities) / float(record_limit))
        current_page = int(current_page)
        start = self.env.company.sh_completed_table * (current_page-1)
        stop = current_page * self.env.company.sh_completed_table
        activities = activities[start:stop]
        return self.env['ir.ui.view'].with_context()._render_template('sh_activities_management_basic.sh_crm_db_activity_completed_tbl', {
            'activities': activities,
            'completed_acitvities_count': total_completed_activities,
            'total_pages': total_pages,
            'current_page': current_page,
        })

    @api.model
    def get_sh_crm_activity_overdue_tbl(self, filter_date, filter_user, start_date, end_date, filter_supervisor, current_page):
        uid = request.session.uid
        user = request.env['res.users'].sudo().browse(uid)
        cids = request.httprequest.cookies.get('cids', str(user.company_id.id))
        cids = [int(cid) for cid in cids.split(',')]
        doman = [('company_id', 'in', cids), ('active', '=', True),
                 ('date_deadline', '<', fields.Date.today())]
        crm_days_filter = filter_date
        custom_date_start = start_date
        custom_date_end = end_date
        if crm_days_filter == 'today':
            dt_flt1 = []
            dt_flt1.append('date_deadline')
            dt_flt1.append('>=')
            dt_flt1.append(datetime.now().date().strftime("%Y/%m/%d"))
            doman.append(tuple(dt_flt1))
            dt_flt2 = []
            dt_flt2.append('date_deadline')
            dt_flt2.append('<=')
            dt_flt2.append(datetime.now().date().strftime("%Y/%m/%d"))
            doman.append(tuple(dt_flt2))
        elif crm_days_filter == 'yesterday':
            dt_flt1 = []
            dt_flt1.append('date_deadline')
            dt_flt1.append('>=')
            prev_day = (datetime.now().date() -
                        relativedelta(days=1)).strftime('%Y/%m/%d')
            dt_flt1.append(prev_day)
            doman.append(tuple(dt_flt1))
            dt_flt2 = []
            dt_flt2.append('date_deadline')
            dt_flt2.append('<=')
            prev_day = (datetime.now().date() -
                        relativedelta(days=1)).strftime('%Y/%m/%d')
            dt_flt2.append(prev_day)
            doman.append(tuple(dt_flt2))
        elif crm_days_filter == 'weekly':  # current week
            dt_flt1 = []
            dt_flt1.append('date_deadline')
            dt_flt1.append('>')
            dt_flt1.append(
                (datetime.now().date() - relativedelta(weeks=1, weekday=0)).strftime("%Y/%m/%d"))
            doman.append(tuple(dt_flt1))
            dt_flt2 = []
            dt_flt2.append('date_deadline')
            dt_flt2.append('<=')
            dt_flt2.append(datetime.now().date().strftime("%Y/%m/%d"))
            doman.append(tuple(dt_flt2))
        elif crm_days_filter == 'prev_week':  # Previous week
            dt_flt1 = []
            dt_flt1.append('date_deadline')
            dt_flt1.append('>')
            dt_flt1.append(
                (datetime.now().date() - relativedelta(weeks=2, weekday=0)).strftime("%Y/%m/%d"))
            doman.append(tuple(dt_flt1))
            dt_flt2 = []
            dt_flt2.append('date_deadline')
            dt_flt2.append('<=')
            dt_flt2.append(
                (datetime.now().date() - relativedelta(weeks=1, weekday=6)).strftime("%Y/%m/%d"))
            doman.append(tuple(dt_flt2))
        elif crm_days_filter == 'monthly':  # Current Month
            dt_flt1 = []
            dt_flt1.append('date_deadline')
            dt_flt1.append('>')
            dt_flt1.append((datetime.now().date()).strftime("%Y/%m/01"))
            doman.append(tuple(dt_flt1))
            dt_flt2 = []
            dt_flt2.append('date_deadline')
            dt_flt2.append('<=')
            dt_flt2.append(datetime.now().date().strftime("%Y/%m/%d"))
            doman.append(tuple(dt_flt2))
        elif crm_days_filter == 'prev_month':  # Previous Month
            dt_flt1 = []
            dt_flt1.append('date_deadline')
            dt_flt1.append('>')
            dt_flt1.append(
                (datetime.now().date() - relativedelta(months=1)).strftime("%Y/%m/01"))
            doman.append(tuple(dt_flt1))
            dt_flt2 = []
            dt_flt2.append('date_deadline')
            dt_flt2.append('<')
            dt_flt2.append(datetime.now().date().strftime("%Y/%m/01"))
            doman.append(tuple(dt_flt2))
        elif crm_days_filter == 'cur_year':  # Current Year
            dt_flt1 = []
            dt_flt1.append('date_deadline')
            dt_flt1.append('>')
            dt_flt1.append((datetime.now().date()).strftime("%Y/01/01"))
            doman.append(tuple(dt_flt1))
            dt_flt2 = []
            dt_flt2.append('date_deadline')
            dt_flt2.append('<=')
            dt_flt2.append(datetime.now().date().strftime("%Y/%m/%d"))
            doman.append(tuple(dt_flt2))
        elif crm_days_filter == 'prev_year':  # Previous Year
            dt_flt1 = []
            dt_flt1.append('date_deadline')
            dt_flt1.append('>')
            dt_flt1.append(
                (datetime.now().date() - relativedelta(years=1)).strftime("%Y/01/01"))
            doman.append(tuple(dt_flt1))
            dt_flt2 = []
            dt_flt2.append('date_deadline')
            dt_flt2.append('<')
            dt_flt2.append(datetime.now().date().strftime("%Y/01/01"))
            doman.append(tuple(dt_flt2))
        elif crm_days_filter == 'custom':
            if custom_date_start and custom_date_end:
                dt_flt1 = []
                dt_flt1.append('date_deadline')
                dt_flt1.append('>')
                dt_flt1.append(datetime.strptime(
                    str(custom_date_start), DEFAULT_SERVER_DATE_FORMAT).strftime("%Y/%m/%d"))
                doman.append(tuple(dt_flt1))
                dt_flt2 = []
                dt_flt2.append('date_deadline')
                dt_flt2.append('<=')
                dt_flt2.append(datetime.strptime(
                    str(custom_date_end), DEFAULT_SERVER_DATE_FORMAT).strftime("%Y/%m/%d"))
                doman.append(tuple(dt_flt2))
        # FILTER USER
        if filter_user not in ['', "", None, False]:
            doman.append(('|'))
            doman.append(('user_id', '=', int(filter_user)))
            doman.append(('sh_user_ids', 'in', [int(filter_user)]))
        else:
            if self.env.user.has_group('sh_activities_management_basic.group_activity_supervisor') and self.env.user.has_group('sh_activities_management_basic.group_activity_user') and not self.env.user.has_group('sh_activities_management_basic.group_activity_manager'):
                doman.append(('|'))
                doman.append(('|'))
                doman.append(('user_id', '!=', self.env.user.id))
                doman.append(('user_id', '=', self.env.user.id))
                doman.append(('sh_user_ids', 'in', [self.env.user.id]))
            elif not self.env.user.has_group('sh_activities_management_basic.group_activity_supervisor') and self.env.user.has_group('sh_activities_management_basic.group_activity_user') and not self.env.user.has_group('sh_activities_management_basic.group_activity_manager'):
                doman.append(('|'))
                doman.append(('user_id', '=', self.env.user.id))
                doman.append(('sh_user_ids', 'in', [self.env.user.id]))
        if filter_supervisor not in ['', "", None, False]:
            doman.append(('supervisor_id', '=', int(filter_supervisor)))
        else:
            if self.env.user.has_group('sh_activities_management_basic.group_activity_supervisor') and self.env.user.has_group('sh_activities_management_basic.group_activity_user') and not self.env.user.has_group('sh_activities_management_basic.group_activity_manager'):
                doman.append(('|'))
                doman.append(('|'))
                doman.append(('supervisor_id', '=', self.env.user.id))
                doman.append(('sh_user_ids', 'in', [self.env.user.id]))
                doman.append(('user_id', '=', self.env.user.id))
            elif not self.env.user.has_group('sh_activities_management_basic.group_activity_supervisor') and self.env.user.has_group('sh_activities_management_basic.group_activity_user') and not self.env.user.has_group('sh_activities_management_basic.group_activity_manager'):
                doman.append(('|'))
                doman.append(('|'))
                doman.append(('supervisor_id', '=', self.env.user.id))
                doman.append(('supervisor_id', '!=', self.env.user.id))
                doman.append(('supervisor_id', '=', False))
        
        # -------------------------------------
        # ALL ACTIVITES
        # -------------------------------------

        from_clause, where_clause_all_activities, where_params_all_activities = self.env['mail.activity']._where_calc(doman).get_sql()

        query = f'''
            SELECT "mail_activity".id FROM "mail_activity" WHERE {where_clause_all_activities}
        '''

        self.env.cr.execute(query, where_params_all_activities)    
        result_all = self._cr.fetchall()

        all_activities_ids = ([r[0] for r in result_all])
        activities = self.env['mail.activity'].browse(all_activities_ids)

        # return {}

        # -------------------------------------
        # ALL ACTIVITES
        # -------------------------------------

        total_pages = 0.0
        total_overdue_activities = len(all_activities_ids)
        record_limit = self.env.company.sh_planned_table
        if total_overdue_activities > 0 and record_limit > 0:
            total_pages = math.ceil(
                float(total_overdue_activities) / float(record_limit))
        current_page = int(current_page)
        start = self.env.company.sh_due_table * (current_page-1)
        stop = current_page * self.env.company.sh_due_table
        activities = activities[start:stop]
        return self.env['ir.ui.view'].with_context()._render_template('sh_activities_management_basic.sh_crm_db_activity_overdue_tbl', {
            'activities': activities,
            'overdue_acitvities_count': total_overdue_activities,
            'total_pages': total_pages,
            'current_page': current_page,
        })

    @api.model
    def get_sh_crm_activity_cancelled_tbl(self, filter_date, filter_user, start_date, end_date, filter_supervisor, current_page):
        uid = request.session.uid
        user = request.env['res.users'].sudo().browse(uid)
        cids = request.httprequest.cookies.get('cids', str(user.company_id.id))
        cids = [int(cid) for cid in cids.split(',')]
        doman = [('company_id', 'in', cids), ('active',
                                              '=', False), ('state', '=', 'cancel')]
        crm_days_filter = filter_date
        custom_date_start = start_date
        custom_date_end = end_date
        if crm_days_filter == 'today':
            dt_flt1 = []
            dt_flt1.append('date_deadline')
            dt_flt1.append('>=')
            dt_flt1.append(datetime.now().date().strftime("%Y/%m/%d"))
            doman.append(tuple(dt_flt1))
            dt_flt2 = []
            dt_flt2.append('date_deadline')
            dt_flt2.append('<=')
            dt_flt2.append(datetime.now().date().strftime("%Y/%m/%d"))
            doman.append(tuple(dt_flt2))
        elif crm_days_filter == 'yesterday':
            dt_flt1 = []
            dt_flt1.append('date_deadline')
            dt_flt1.append('>=')
            prev_day = (datetime.now().date() -
                        relativedelta(days=1)).strftime('%Y/%m/%d')
            dt_flt1.append(prev_day)
            doman.append(tuple(dt_flt1))
            dt_flt2 = []
            dt_flt2.append('date_deadline')
            dt_flt2.append('<=')
            prev_day = (datetime.now().date() -
                        relativedelta(days=1)).strftime('%Y/%m/%d')
            dt_flt2.append(prev_day)
            doman.append(tuple(dt_flt2))
        elif crm_days_filter == 'weekly':  # current week
            dt_flt1 = []
            dt_flt1.append('date_deadline')
            dt_flt1.append('>')
            dt_flt1.append(
                (datetime.now().date() - relativedelta(weeks=1, weekday=0)).strftime("%Y/%m/%d"))
            doman.append(tuple(dt_flt1))
            dt_flt2 = []
            dt_flt2.append('date_deadline')
            dt_flt2.append('<=')
            dt_flt2.append(datetime.now().date().strftime("%Y/%m/%d"))
            doman.append(tuple(dt_flt2))
        elif crm_days_filter == 'prev_week':  # Previous week
            dt_flt1 = []
            dt_flt1.append('date_deadline')
            dt_flt1.append('>')
            dt_flt1.append(
                (datetime.now().date() - relativedelta(weeks=2, weekday=0)).strftime("%Y/%m/%d"))
            doman.append(tuple(dt_flt1))
            dt_flt2 = []
            dt_flt2.append('date_deadline')
            dt_flt2.append('<=')
            dt_flt2.append(
                (datetime.now().date() - relativedelta(weeks=1, weekday=6)).strftime("%Y/%m/%d"))
            doman.append(tuple(dt_flt2))
        elif crm_days_filter == 'monthly':  # Current Month
            dt_flt1 = []
            dt_flt1.append('date_deadline')
            dt_flt1.append('>')
            dt_flt1.append((datetime.now().date()).strftime("%Y/%m/01"))
            doman.append(tuple(dt_flt1))
            dt_flt2 = []
            dt_flt2.append('date_deadline')
            dt_flt2.append('<=')
            dt_flt2.append(datetime.now().date().strftime("%Y/%m/%d"))
            doman.append(tuple(dt_flt2))
        elif crm_days_filter == 'prev_month':  # Previous Month
            dt_flt1 = []
            dt_flt1.append('date_deadline')
            dt_flt1.append('>')
            dt_flt1.append(
                (datetime.now().date() - relativedelta(months=1)).strftime("%Y/%m/01"))
            doman.append(tuple(dt_flt1))
            dt_flt2 = []
            dt_flt2.append('date_deadline')
            dt_flt2.append('<')
            dt_flt2.append(datetime.now().date().strftime("%Y/%m/01"))
            doman.append(tuple(dt_flt2))
        elif crm_days_filter == 'cur_year':  # Current Year
            dt_flt1 = []
            dt_flt1.append('date_deadline')
            dt_flt1.append('>')
            dt_flt1.append((datetime.now().date()).strftime("%Y/01/01"))
            doman.append(tuple(dt_flt1))
            dt_flt2 = []
            dt_flt2.append('date_deadline')
            dt_flt2.append('<=')
            dt_flt2.append(datetime.now().date().strftime("%Y/%m/%d"))
            doman.append(tuple(dt_flt2))
        elif crm_days_filter == 'prev_year':  # Previous Year
            dt_flt1 = []
            dt_flt1.append('date_deadline')
            dt_flt1.append('>')
            dt_flt1.append(
                (datetime.now().date() - relativedelta(years=1)).strftime("%Y/01/01"))
            doman.append(tuple(dt_flt1))
            dt_flt2 = []
            dt_flt2.append('date_deadline')
            dt_flt2.append('<')
            dt_flt2.append(datetime.now().date().strftime("%Y/01/01"))
            doman.append(tuple(dt_flt2))
        elif crm_days_filter == 'custom':
            if custom_date_start and custom_date_end:
                dt_flt1 = []
                dt_flt1.append('date_deadline')
                dt_flt1.append('>')
                dt_flt1.append(datetime.strptime(
                    str(custom_date_start), DEFAULT_SERVER_DATE_FORMAT).strftime("%Y/%m/%d"))
                doman.append(tuple(dt_flt1))
                dt_flt2 = []
                dt_flt2.append('date_deadline')
                dt_flt2.append('<=')
                dt_flt2.append(datetime.strptime(
                    str(custom_date_end), DEFAULT_SERVER_DATE_FORMAT).strftime("%Y/%m/%d"))
                doman.append(tuple(dt_flt2))
        # FILTER USER
        if filter_user not in ['', "", None, False]:
            doman.append(('|'))
            doman.append(('user_id', '=', int(filter_user)))
            doman.append(('sh_user_ids', 'in', [int(filter_user)]))
        else:
            if self.env.user.has_group('sh_activities_management_basic.group_activity_supervisor') and self.env.user.has_group('sh_activities_management_basic.group_activity_user') and not self.env.user.has_group('sh_activities_management_basic.group_activity_manager'):
                doman.append(('|'))
                doman.append(('|'))
                doman.append(('user_id', '!=', self.env.user.id))
                doman.append(('user_id', '=', self.env.user.id))
                doman.append(('sh_user_ids', 'in', [self.env.user.id]))
            elif not self.env.user.has_group('sh_activities_management_basic.group_activity_supervisor') and self.env.user.has_group('sh_activities_management_basic.group_activity_user') and not self.env.user.has_group('sh_activities_management_basic.group_activity_manager'):
                doman.append(('|'))
                doman.append(('user_id', '=', self.env.user.id))
                doman.append(('sh_user_ids', 'in', [self.env.user.id]))
        if filter_supervisor not in ['', "", None, False]:
            doman.append(('supervisor_id', '=', int(filter_supervisor)))
        else:
            if self.env.user.has_group('sh_activities_management_basic.group_activity_supervisor') and self.env.user.has_group('sh_activities_management_basic.group_activity_user') and not self.env.user.has_group('sh_activities_management_basic.group_activity_manager'):
                doman.append(('|'))
                doman.append(('|'))
                doman.append(('supervisor_id', '=', self.env.user.id))
                doman.append(('sh_user_ids', 'in', [self.env.user.id]))
                doman.append(('user_id', '=', self.env.user.id))
            elif not self.env.user.has_group('sh_activities_management_basic.group_activity_supervisor') and self.env.user.has_group('sh_activities_management_basic.group_activity_user') and not self.env.user.has_group('sh_activities_management_basic.group_activity_manager'):
                doman.append(('|'))
                doman.append(('|'))
                doman.append(('supervisor_id', '=', self.env.user.id))
                doman.append(('supervisor_id', '!=', self.env.user.id))
                doman.append(('supervisor_id', '=', False))
        
        # -------------------------------------
        # ALL ACTIVITES
        # -------------------------------------

        from_clause, where_clause_all_activities, where_params_all_activities = self.env['mail.activity']._where_calc(doman).get_sql()

        query = f'''
            SELECT "mail_activity".id FROM "mail_activity" WHERE {where_clause_all_activities}
        '''

        self.env.cr.execute(query, where_params_all_activities)    
        result_all = self._cr.fetchall()

        all_activities_ids = [r[0] for r in result_all]
        activities = self.env['mail.activity'].browse(all_activities_ids)

        # return {}

        # -------------------------------------
        # ALL ACTIVITES
        # -------------------------------------

        total_pages = 0.0
        total_cancelled_activities = len(all_activities_ids)
        record_limit = self.env.company.sh_cancel_table
        if total_cancelled_activities > 0 and record_limit > 0:
            total_pages = math.ceil(
                float(total_cancelled_activities) / float(record_limit))
        current_page = int(current_page)
        start = self.env.company.sh_cancel_table * (current_page-1)
        stop = current_page * self.env.company.sh_cancel_table
        activities = activities[start:stop]
        return self.env['ir.ui.view'].with_context()._render_template('sh_activities_management_basic.sh_crm_db_activity_cancelled_tbl', {
            'activities': activities,
            'cancelled_acitvities_count': total_cancelled_activities,
            'total_pages': total_pages,
            'current_page': current_page,
        })

    @api.model
    def get_user_list(self):
        uid = request.session.uid
        user = request.env['res.users'].sudo().browse(uid)
        cids = request.httprequest.cookies.get('cids', str(user.company_id.id))
        cids = [int(cid) for cid in cids.split(',')]
        all_user = {}

        domain_user = [
            ('company_ids', 'in', cids),
            ('share', '=', False),
            ('groups_id', 'in', self.env.ref(
                'sh_activities_management_basic.group_activity_user').id)
        ]

        domain_supervisor = [
            ('company_ids', 'in', cids),
            ('share', '=', False),
            ('groups_id', 'in', self.env.ref(
                'sh_activities_management_basic.group_activity_supervisor').id)
        ]

        users = self.env["res.users"].sudo().search_read(
            domain_user, ['id', 'name'])

        supervisors = self.env["res.users"].sudo().search_read(
            domain_supervisor, ['id', 'name'])

        # all_user.update{'users':users}

        all_user.update({'users': users, 'supervisors': supervisors})
        return all_user


class MergePartnerAutomaticCustom(models.TransientModel):
    _inherit = 'base.partner.merge.automatic.wizard'

    def _merge(self, partner_ids, dst_partner=None, extra_checks=True):
        """ private implementation of merge partner
            :param partner_ids : ids of partner to merge
            :param dst_partner : record of destination res.partner
            :param extra_checks: pass False to bypass extra sanity check (e.g. email address)
        """
        # super-admin can be used to bypass extra checks
        if self.env.is_admin():
            extra_checks = False

        Partner = self.env['res.partner']
        partner_ids = Partner.browse(partner_ids).exists()
        if len(partner_ids) < 2:
            return

        if len(partner_ids) > 3:
            raise UserError(
                _("For safety reasons, you cannot merge more than 3 contacts together. You can re-open the wizard several times if needed."))

        # check if the list of partners to merge contains child/parent relation
        child_ids = self.env['res.partner']
        for partner_id in partner_ids:
            child_ids |= Partner.search(
                [('id', 'child_of', [partner_id.id])]) - partner_id
        if partner_ids & child_ids:
            raise UserError(
                _("You cannot merge a contact with one of his parent."))

        if extra_checks and len(set(partner.email for partner in partner_ids)) > 1:
            raise UserError(
                _("All contacts must have the same email. Only the Administrator can merge contacts with different emails."))

        # remove dst_partner from partners to merge
        if dst_partner and dst_partner in partner_ids:
            src_partners = partner_ids - dst_partner
        else:
            ordered_partners = self._get_ordered_partner(partner_ids.ids)
            dst_partner = ordered_partners[-1]
            src_partners = ordered_partners[:-1]
        _logger.info("dst_partner: %s", dst_partner.id)

        # FIXME: is it still required to make and exception for account.move.line since accounting v9.0 ?
        if extra_checks and 'account.move.line' in self.env and self.env['account.move.line'].sudo().search([('partner_id', 'in', [partner.id for partner in src_partners])]):
            raise UserError(
                _("Only the destination contact may be linked to existing Journal Items. Please ask the Administrator if you need to merge several contacts linked to existing Journal Items."))

        # Make the company of all related users consistent with destination partner company
        if dst_partner.company_id:
            partner_ids.mapped('user_ids').sudo().write({
                'company_ids': [Command.link(dst_partner.company_id.id)],
                'company_id': dst_partner.company_id.id
            })

        # --------------------------------
        # CUSTOM CHANGES
        # --------------------------------

        if dst_partner.activity_ids:
            for activity in dst_partner.activity_ids:
                activity.res_id = dst_partner.id
        if src_partners.activity_ids:
            for activity in src_partners.activity_ids:
                activity.res_id = dst_partner.id

        # call sub methods to do the merge
        self._update_foreign_keys(src_partners, dst_partner)
        # self._update_reference_fields(src_partners, dst_partner)
        self._update_values(src_partners, dst_partner)

        self._log_merge_operation(src_partners, dst_partner)

        # delete source partner, since they are merged
        src_partners.unlink()
