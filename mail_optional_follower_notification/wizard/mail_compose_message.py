# Copyright 2016 ACSONE SA/NV (<http://acsone.eu>)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import logging
from odoo import fields, models, api, Command

_logger = logging.getLogger(__name__)

class AccountMoveSend(models.TransientModel):
    _inherit = 'account.move.send'


    @api.model
    def _send_mail(self, move, mail_template, **kwargs):
        partner_ids = kwargs.get('partner_ids', [])
        author_id = kwargs.pop('author_id', False)
        kwargs.pop('recipient_ids', None)
        new_message = move.with_context(
            no_new_invoice=True,
            mail_notify_author=author_id in partner_ids,
            mail_post_autofollow=False, # evita a los followers
            mail_notify_force_send=True,
            no_notify_followers=True,  # 👈 contexto clave
            allowed_partner_ids=partner_ids,
        ).message_post(
            message_type='comment',
            **kwargs,
            **{
                'email_layout_xmlid': self._get_mail_layout(),
                'email_add_signature': not mail_template,
                'mail_auto_delete': mail_template.auto_delete,
                'mail_server_id': mail_template.mail_server_id.id,
                'reply_to_force_new': False,
            },
        )

    """            METODO ORIGINAL
    @api.model
    def _send_mail(self, move, mail_template, **kwargs):
        partner_ids = kwargs.get('partner_ids', [])
        author_id = kwargs.pop('author_id')
        new_message = move\
            .with_context(
                no_new_invoice=True,
                mail_notify_author=author_id in partner_ids,
            ).message_post(
                message_type='comment',
                **kwargs,
                **{
                    'email_layout_xmlid': self._get_mail_layout(),
                    'email_add_signature': not mail_template,
                    'mail_auto_delete': mail_template.auto_delete,
                    'mail_server_id': mail_template.mail_server_id.id,
                    'reply_to_force_new': False,
                },
            )

        # Prevent duplicated attachments linked to the invoice.
        new_message.attachment_ids.invalidate_recordset(['res_id', 'res_model'], flush=False)
        if new_message.attachment_ids.ids:
            self.env.cr.execute("UPDATE ir_attachment SET res_id = NULL WHERE id IN %s", [tuple(new_message.attachment_ids.ids)])
        new_message.attachment_ids.write({
            'res_model': new_message._name,
            'res_id': new_message.id,
        })"""

class MailMail(models.Model):
    _inherit = 'mail.mail'

    @api.model
    def create(self, vals):
        if self.env.context.get('no_notify_followers'):
            allowed_partners = set(self.env.context.get('allowed_partner_ids', []))
            res_model = vals.get('model')
            res_id = vals.get('res_id')
            recipient_ids = vals.get('recipient_ids', [])

            recipient_ids = vals.get('recipient_ids', [])
            partner_ids = [cmd[1] for cmd in recipient_ids if isinstance(cmd, (list, tuple)) and cmd[0] == 4]

            # Obtener o inicializar el contexto de control
            if 'mail_send_cache' not in self.env.context:
                # Si 'mail_send_cache' no está en el contexto, crea un nuevo contexto
                # con el valor y úsalo. Esto asegura que el contexto no sea frozendict
                # si necesitas modificarlo, o lo modifica inmutablemente.
                new_context = self.env.context.copy() # Crea una copia mutable
                new_context['mail_send_cache'] = set()
                self = self.with_context(new_context)
            sent_keys = self.env.context.get('mail_send_cache')

            filtered = []
            for pid in partner_ids:
                key = (res_model, res_id, pid)
                if key not in sent_keys and pid in allowed_partners:
                    sent_keys.add(key)
                    filtered.append(pid)

            if not filtered:
                return self.env['mail.mail'].browse()  # No enviar duplicado en esta ejecución

            vals['recipient_ids'] = [(4, pid) for pid in filtered]

            # Propagamos el contexto actualizado
            return super(MailMail, self.with_context(mail_send_cache=sent_keys)).create(vals)

        return super().create(vals)

    
class MailComposeMessage(models.TransientModel):
    _inherit = "mail.compose.message"

    notify_followers = fields.Boolean(
        default=lambda self: self.env.company.notify_followers
    )

    def _action_send_mail(self, auto_commit=False):
        print ('==========================')
        result_mails_su, result_messages = (
            self.env["mail.mail"].sudo(),
            self.env["mail.message"],
        )
        for wizard in self:
            wizard = wizard.with_context(notify_followers=wizard.notify_followers)
            res_mail, res_message = super(MailComposeMessage, wizard)._action_send_mail(
                auto_commit=auto_commit
            )
            result_mails_su += res_mail
            result_messages += res_message
        return result_mails_su, result_messages


    def get_mail_values(self, res_ids):
        mail_values = super().get_mail_values(res_ids)
        print ('---------------',mail_values)
        for res_id in res_ids:
            values = mail_values[res_id]
            # Filtra solo para modelos específicos como sale.order o account.move
            if self.model in ['sale.order', 'account.move']:
                # Forzamos que solo se envíe al partner_id
                partner_id = self.env[self.model].browse(res_id).partner_id
                values['partner_ids'] = [(4, partner_id.id)]
                values['email_to'] = partner_id.email or ''
                values['email_cc'] = ''
                values['recipient_ids'] = []  # Limpiar los seguidores (message_follower_ids)

            mail_values[res_id] = values
        return mail_values
