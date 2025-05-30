================================
Mail Notification Custom Subject
================================

.. 
   !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
   !! This file is generated by oca-gen-addon-readme !!
   !! changes will be overwritten.                   !!
   !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
   !! source digest: sha256:7aee6560ed9da6ebf673ad8d958f4209625bcab1cd2ecff4a748a5efa3809447
   !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

.. |badge1| image:: https://img.shields.io/badge/maturity-Production%2FStable-green.png
    :target: https://odoo-community.org/page/development-status
    :alt: Production/Stable
.. |badge2| image:: https://img.shields.io/badge/licence-AGPL--3-blue.png
    :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
    :alt: License: AGPL-3
.. |badge3| image:: https://img.shields.io/badge/github-OCA%2Fsocial-lightgray.png?logo=github
    :target: https://github.com/OCA/social/tree/17.0/mail_notification_custom_subject
    :alt: OCA/social
.. |badge4| image:: https://img.shields.io/badge/weblate-Translate%20me-F47D42.png
    :target: https://translation.odoo-community.org/projects/social-17-0/social-17-0-mail_notification_custom_subject
    :alt: Translate me on Weblate
.. |badge5| image:: https://img.shields.io/badge/runboat-Try%20me-875A7B.png
    :target: https://runboat.odoo-community.org/builds?repo=OCA/social&target_branch=17.0
    :alt: Try me on Runboat

|badge1| |badge2| |badge3| |badge4| |badge5|

This module allows you to specify templates to override the subject on
the notification emails sent by Odoo

**Table of contents**

.. contents::
   :local:

Configuration
=============

- Activate access to **Technical Features** (debug mode).

- Go to **Settings > Technical > Email > Subject Replacement Templates**

- Create a new template.

     - The field **Model** specifies the model to which the subject
       template should apply in the notification emails sent by Odoo.
     - The field **Subject Template** accepts
       `expressions <https://www.odoo.com/documentation/17.0/applications/general/companies/email_template.html#dynamic-placeholders>`__.
     - The field **Subject to replace** accepts
       `expressions <https://www.odoo.com/documentation/17.0/applications/general/companies/email_template.html#dynamic-placeholders>`__
     - The field **Replace** specifies if the template should replace
       existing content or append to it.
     - The field **Partial Replacement** specifies if the template
       should parcial replace existing content.

Usage
=====

To use this module, you need to:

- Open the chatter in Odoo (e.g. Open an Invoice).
- Send a message.
- Observe the rendered Subject template.

Bug Tracker
===========

Bugs are tracked on `GitHub Issues <https://github.com/OCA/social/issues>`_.
In case of trouble, please check there if your issue has already been reported.
If you spotted it first, help us to smash it by providing a detailed and welcomed
`feedback <https://github.com/OCA/social/issues/new?body=module:%20mail_notification_custom_subject%0Aversion:%2017.0%0A%0A**Steps%20to%20reproduce**%0A-%20...%0A%0A**Current%20behavior**%0A%0A**Expected%20behavior**>`_.

Do not contact contributors directly about support or help with technical issues.

Credits
=======

Authors
-------

* Tecnativa

Contributors
------------

- Tecnativa <https://www.tecnativa.com>

     - Pedro M. Baeza
     - João Marques
     - Carlos Roca
     - Víctor Martínez

- Versada <https://versada.eu>

  - Naglis Jonaitis

- Moduon <https://www.moduon.team>

  - Eduardo de Miguel

Maintainers
-----------

This module is maintained by the OCA.

.. image:: https://odoo-community.org/logo.png
   :alt: Odoo Community Association
   :target: https://odoo-community.org

OCA, or the Odoo Community Association, is a nonprofit organization whose
mission is to support the collaborative development of Odoo features and
promote its widespread use.

.. |maintainer-victoralmau| image:: https://github.com/victoralmau.png?size=40px
    :target: https://github.com/victoralmau
    :alt: victoralmau
.. |maintainer-sergio-teruel| image:: https://github.com/sergio-teruel.png?size=40px
    :target: https://github.com/sergio-teruel
    :alt: sergio-teruel

Current `maintainers <https://odoo-community.org/page/maintainer-role>`__:

|maintainer-victoralmau| |maintainer-sergio-teruel| 

This module is part of the `OCA/social <https://github.com/OCA/social/tree/17.0/mail_notification_custom_subject>`_ project on GitHub.

You are welcome to contribute. To learn how please visit https://odoo-community.org/page/Contribute.
