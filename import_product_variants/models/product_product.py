from odoo import api, fields, models, _
import json


class ProductProduct(models.Model):
    _inherit = 'product.product'

    combination_names = fields.Char(compute='_compute_combination_names', store=True, index=True)
    last_excel_update = fields.Datetime(copy=False)

    @api.model
    def open_product_import_wizard(self):
        action = self.env.ref('import_product_variants.product_product_import_variants_action')
        result = action.read()[0]
        return result

    @api.depends('product_template_attribute_value_ids')
    def _compute_combination_names(self):
        for product in self.with_context(lang='es_MX'):
            names = ""
            if product.product_template_attribute_value_ids:
                combination_names = {attribute.attribute_id.name: attribute.name for attribute in
                                     product.product_template_attribute_value_ids}
                names = json.dumps(combination_names, sort_keys=True)
            product.combination_names = names

    @api.model
    def create(self, values):
        if self._context.get('is_created_excel'):
            values['last_excel_update'] = fields.Date.context_today(self)
        return super(ProductProduct, self).create(values)


class ProductTemplate(models.Model):
    _name = "product.template"
    _inherit = "product.template"

    default_code = fields.Char('Internal Reference', store=True, compute=False, inverse=False)
