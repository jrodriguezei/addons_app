# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
from collections import defaultdict
from odoo import fields, models,tools
from odoo.addons.web_editor.models.ir_qweb_fields import html_to_text

class MailActivity(models.Model):
    _inherit = 'mail.activity'

    feedback = fields.Char()

    def get_feedback(self):        
        feedback = tools.html_to_inner_content(self.# In the provided code snippet, the `feedback`
        # parameter is used in the `_action_done` method
        # of the `MailActivity` model. This method is a
        # private implementation for marking an activity
        # as done. The `feedback` parameter is optional
        # and represents any feedback provided by the user
        # when marking the activity as done.
        feedback)      
        return feedback

    def get_note(self):
        note = tools.html_to_inner_content(self.note)      
        return note

    def write(self, values):
        res = super(MailActivity, self.sudo()).write(values)
        if not values.get('feedback', False):
            if self.env.user.company_id.activity_email_notification and self.env.user.company_id.edit_notification:
                if self.create_uid != self.user_id:
                    if self.env.user.company_id.notify_create_user_edit:
                        template = self.env.ref(
                            'sh_activity_notify_emails.send_activity_notification_create_user')
                        self.env['mail.template'].sudo().browse(template.id).with_context(
                            edit_activity=True, user=self.env.user.name).send_mail(self.id, force_send=True)
                    if self.env.user.company_id.notify_assignee_user_edit:
                        template = self.env.ref(
                            'sh_activity_notify_emails.send_activity_notification_assignee')
                        self.env['mail.template'].sudo().browse(template.id).with_context(
                            edit_activity=True, user=self.env.user.name).sudo().send_mail(self.id, force_send=True)
                else:
                    if self.env.user.company_id.notify_create_user_edit or self.env.user.company_id.notify_assignee_user_edit:
                        template = self.env.ref(
                            'sh_activity_notify_emails.send_activity_notification_create_user')
                        self.env['mail.template'].sudo().browse(template.id).with_context(
                            edit_activity=True, user=self.env.user.name).send_mail(self.id, force_send=True)
        return res

    def unlink(self):
        for activity in self:
            if 'done_act' not in self._context:

                if self.env.user.company_id.activity_email_notification and self.env.user.company_id.cancel_notification:
                    if self.create_uid != self.user_id:
                        if self.env.user.company_id.notify_create_user_cancel:
                            template = self.env.ref(
                                'sh_activity_notify_emails.send_activity_notification_create_user')
                            self.env['mail.template'].sudo().browse(template.id).with_context(
                                unlink_activity=True, user=self.env.user.name).send_mail(activity.id, force_send=True)
                        if self.env.user.company_id.notify_assignee_user_cancel:
                            template = self.env.ref(
                                'sh_activity_notify_emails.send_activity_notification_assignee')
                            self.env['mail.template'].sudo().browse(template.id).with_context(
                                unlink_activity=True, user=activity.user_id.name).send_mail(activity.id, force_send=True)
                    else:
                        if self.env.user.company_id.notify_create_user_cancel or self.env.user.company_id.notify_assignee_user_cancel:                            
                            if self.env.user.company_id.notify_create_user_cancel:
                                template = self.env.ref(
                                    'sh_activity_notify_emails.send_activity_notification_create_user')
                                self.env['mail.template'].sudo().browse(template.id).with_context(
                                    unlink_activity=True, user=self.env.user.name).send_mail(activity.id, force_send=True)
                            if self.env.user.company_id.notify_assignee_user_cancel:
                                template = self.env.ref(
                                    'sh_activity_notify_emails.send_activity_notification_create_user')
                                self.env['mail.template'].sudo().browse(template.id).with_context(
                                    unlink_activity=True, user=activity.user_id.name).send_mail(activity.id, force_send=True)

        return super(MailActivity, self.sudo()).unlink()
     

    def _action_done(self, feedback=False, attachment_ids=None):
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
        self.feedback = feedback if feedback else  ' '
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

        for model, activity_data in self._classify_by_model().items():
            records = self.env[model].browse(activity_data['record_ids'])
            for record, activity in zip(records, activity_data['activities']):
                # extract value to generate next activities
                if activity.chaining_type == 'trigger':
                    vals = activity.with_context(activity_previous_deadline=activity.date_deadline)._prepare_next_activity_values()
                    next_activities_values.append(vals)

                # post message on activity, before deleting it
                activity_message = record.message_post_with_source(
                    'mail.message_activity_done',
                    attachment_ids=attachment_ids,
                    render_values={
                        'activity': activity,
                        'feedback': feedback,
                        'display_assignee': activity.user_id != self.env.user
                    },
                    mail_activity_type_id=activity.activity_type_id.id,
                    subtype_xmlid='mail.mt_activities',
                )

                # Moving the attachments in the message
                # TODO: Fix void res_id on attachment when you create an activity with an image
                # directly, see route /web_editor/attachment/add
                if activity_attachments[activity.id]:
                    message_attachments = self.env['ir.attachment'].browse(activity_attachments[activity.id])
                    if message_attachments:
                        message_attachments.write({
                            'res_id': activity_message.id,
                            'res_model': activity_message._name,
                        })
                        activity_message.attachment_ids = message_attachments
                messages += activity_message

        next_activities = self.env['mail.activity']
        if next_activities_values:
            next_activities = self.env['mail.activity'].create(next_activities_values)

        if self.env.user.company_id.activity_email_notification and self.env.user.company_id.done_notification:
            if self.create_uid != self.user_id:
                if self.env.user.company_id.notify_assignee_user_done:
                    template = self.env.ref(
                        'sh_activity_notify_emails.send_activity_notification_assignee')
                    # Send out the e-mail template to the user
                    self.env['mail.template'].sudo().browse(template.id).with_context(
                        done_activity=True, user=self.env.user.name).send_mail(self.id, force_send=True)
                if self.env.user.company_id.notify_create_user_done:
                    template = self.env.ref(
                        'sh_activity_notify_emails.send_activity_notification_create_user')
                    # Send out the e-mail template to the user
                    self.env['mail.template'].sudo().browse(template.id).with_context(
                        done_activity=True, user=self.env.user.name).send_mail(self.id, force_send=True)
            else:
                if self.env.user.company_id.notify_assignee_user_done or self.env.user.company_id.notify_create_user_done:
                    template = self.env.ref(
                        'sh_activity_notify_emails.send_activity_notification_assignee')
                    # Send out the e-mail template to the user
                    self.env['mail.template'].sudo().browse(template.id).with_context(
                        done_activity=True, user=self.env.user.name).send_mail(self.id, force_send=True)

        self.unlink()  # will unlink activity, dont access `self` after that

        return messages, next_activities
