from odoo import api, fields, models, _


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    is_excel_import = fields.Boolean(string="Se importo por excel?", copy=False)

    @api.model
    def open_purchase_import_wizard(self):
        action = self.env.ref('import_product_variants.purchase_order_import_variants_action')
        result = action.read()[0]
        return result


