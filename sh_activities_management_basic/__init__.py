# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from . import wizard
from . import models
from odoo import api, fields, SUPERUSER_ID, _


def uninstall_hook(env):
    activity_rule = env.ref('mail.mail_activity_rule_user')
    if activity_rule:
        activity_rule.write({
            'domain_force':"['|', ('user_id', '=', user.id), ('create_uid', '=', user.id)]"
        })
