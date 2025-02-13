{
    'name': 'Comarch Exchange',
    'author': 'Mayla Software EOOD',
    'website': 'https://maylasoftware.com/comarch-edi-odoo-connector',
    'category': 'Services',
    'summery': 'Comarch EDI connector. This module provides data exchange between Comarch EDI ECOD platform and ODOO',
    'description': """Comarch EDI connector. This module provides data exchange between Comarch EDI ECOD platform and ODOO
    The synchronization is working as follows:
                    <br>
                    The orders are imported from Comarch Exchange to Odoo.
                    <br>
                    The stock moves are exported from Odoo to Comarch Exchange.
                    <br>
                    The invoices are exported from Odoo to Comarch Exchange.
    """,
    'support': 'd.lyubenov@maylasoftware.com',
    'images': ['static/description/banner.png'],
    'license': 'OPL-1',
    'version': '1.0.0',
    'depends': ['mail', 'portal', 'account', 'sale', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
        'views/data_task_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'comarch_exchange/static/src/js/*.js',
            'comarch_exchange/static/src/xml/*.xml',
        ],
    },
    'installable': True,
    'application': True,
}
