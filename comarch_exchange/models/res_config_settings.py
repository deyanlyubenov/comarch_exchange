from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    comarch_service_license_key = fields.Char(string='Comarch Service License Key',
                                                 config_parameter='comarch_exchange.comarch_service_licanse_key')
