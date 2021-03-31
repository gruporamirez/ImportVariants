import xlrd
import base64
import io
import datetime
import json
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import config, DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, pycompat


# this can be in /wizard but im to lazy


class PurchaseOrderImport(models.TransientModel):
    _name = 'purchase.order.import.variants'
    _description = "Wizard to import Purchase Order with product variants in custom layout excel"

    name = fields.Char("Import Name", compute="_get_import_name")
    excel_file = fields.Binary(string="Excel to Import", )
    excel_filename = fields.Char(string="FileName")
    include_title = fields.Boolean(string="Include Column Names", default=True)
    include_variants = fields.Boolean(string="Include variants?")
    purchase_ids = fields.Many2many(comodel_name="purchase.order", relation="purchase_import_variants_relation",
                                    string="Ordenes Creadas", )
    count_purchases = fields.Integer(required=False, compute="_compute_total_count")

    @api.depends('count_purchases')
    def _compute_total_count(self):
        for record in self:
            record.count_purchases = len(record.purchase_ids)

    @api.depends('excel_filename')
    def _get_import_name(self):
        for record in self:
            record.name = record.excel_filename or "Not defined"

    def open_purchase_views(self):

        action = {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'name': "Compras Creadas",
            'view_id': False,
            'view_type': 'list',
            'view_mode': 'tree',
            'views': [(False, "list"), (False, "form")],
            'domain': [('id', 'in', self.purchase_ids.ids)],

        }
        return action

    def validate_excel(self):
        if not self.excel_file:
            raise UserError(_("Error: No hay un archivo adjuntado"))
        if '.xls' not in self.excel_filename:
            raise UserError(_("Error: El archivo no es .xls o xlsx"))

    def get_dict_from_row_values(self, row_data):
        # check if is purchase order  or purchase order line. we check if partner_id exists
        if row_data[2]:
            return {
                'partner_ref': row_data[0],
                'date_order': row_data[1],
                'partner_id': self.env['res.partner'].search([('name', '=', row_data[2])],
                                                             limit=1).id,
                'user_id': self.env['res.users'].search([('name', '=', row_data[3])], limit=1).id,
                'currency_id': self.env['res.currency'].search([('name', '=', str(row_data[4]))], limit=1).id,
                'order_line': [(0, 0, {
                    'product_qty': float(row_data[5]),
                    'product_id': self.env['product.product'].search([('barcode', '=', row_data[6])], limit=1).id,
                    'name': row_data[7],
                    'price_unit': row_data[8],
                    'date_planned': row_data[9],
                    'product_uom': self.env['uom.uom'].search([('name', '=', str(row_data[10]))], limit=1).id,
                })
                               ],
                'picking_type_id': self.env['stock.picking.type'].search([('display_name', '=', row_data[11])],
                                                                         limit=1).id,
                'is_excel_import': True,
            }
        else:
            return {
                'product_qty': float(row_data[5]),
                'product_id': self.env['product.product'].search([('barcode', '=', row_data[6])], limit=1).id,
                'name': row_data[7],
                'price_unit': row_data[8],
                'date_planned': row_data[9],
                'product_uom': self.env['uom.uom'].search([('name', '=', str(row_data[10]))], limit=1).id,
            }

    def action_import(self):
        self.validate_excel()
        inputx = io.BytesIO()
        inputx.write(base64.decodebytes(self.excel_file))
        book = xlrd.open_workbook(file_contents=inputx.getvalue() or b'')
        rows = [val for val in self._read_xls_book(book)]
        if not rows:
            return False
        if self.include_title:
            rows = rows[1:]
        orders = []
        current_order = {}
        for row in rows:
            if not (row[2] or row[5]):
                continue
            values = self.get_dict_from_row_values(row)
            if row[2]:
                if current_order:
                    orders.append(current_order)
                current_order = values
            elif row[5]:
                current_order['order_line'] = current_order.get('order_line') + [(0, 0, values)]
        if current_order:
            orders.append(current_order)
        created_ids = self.env['purchase.order'].create(orders)
        self.purchase_ids = [(6, 0, created_ids.ids)]
        print(orders)

    def action_import_product(self):
        self.validate_excel()
        self.with_context(lang="es_MX")
        inputx = io.BytesIO()
        inputx.write(base64.decodebytes(self.excel_file))
        book = xlrd.open_workbook(file_contents=inputx.getvalue() or b'')
        rows = [val for val in self._read_xls_book(book)]
        if not rows:
            return False
        if self.include_title:
            rows = rows[1:]
        orders = []
        current_order = {}
        for row in rows:
            if not (row[2] or row[5]):
                continue
            values = self.get_dict_from_row_values_variants(row)
            if row[2]:
                if current_order:
                    orders.append(current_order)
                current_order = values
            elif row[5]:
                current_order['order_line'] = current_order.get('order_line') + [(0, 0, values)]
        if current_order:
            orders.append(current_order)
        created_ids = self.env['purchase.order'].create(orders)
        self.purchase_ids = [(6,0,created_ids.ids)]
        print(orders)

    def _read_xls_book(self, book):
        sheet = book.sheet_by_index(0)
        # emulate Sheet.get_rows for pre-0.9.4
        for rowx, row in enumerate(map(sheet.row, range(sheet.nrows)), 1):
            values = []
            for colx, cell in enumerate(row, 1):
                if cell.ctype is xlrd.XL_CELL_NUMBER:
                    is_float = cell.value % 1 != 0.0
                    values.append(
                        str(cell.value)
                        if is_float
                        else str(int(cell.value))
                    )
                elif cell.ctype is xlrd.XL_CELL_DATE:
                    is_datetime = cell.value % 1 != 0.0
                    # emulate xldate_as_datetime for pre-0.9.3
                    dt = datetime.datetime(*xlrd.xldate.xldate_as_tuple(cell.value, book.datemode))
                    values.append(
                        dt.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
                        if is_datetime
                        else dt.strftime(DEFAULT_SERVER_DATE_FORMAT)
                    )
                elif cell.ctype is xlrd.XL_CELL_BOOLEAN:
                    values.append(u'True' if cell.value else u'False')
                elif cell.ctype is xlrd.XL_CELL_ERROR:
                    raise ValueError(
                        _("Invalid cell value at row %(row)s, column %(col)s: %(cell_value)s") % {
                            'row': rowx,
                            'col': colx,
                            'cell_value': xlrd.error_text_from_code.get(cell.value,
                                                                        _("unknown error code %s") % cell.value)
                        }
                    )
                else:
                    values.append(cell.value)
            if any(x for x in values if x.strip()):
                yield values

    def get_dict_from_row_values_variants(self, row_data):
        # check if is purchase order  or purchase order line. we check if partner_id exists
        product = self.get_product(row_data)
        product.write({
            'barcode': row_data[11],
            'default_code': row_data[12],
            'name': row_data[14],
            'product_brand_id': self.env['product.brand'].search([('name', '=', row_data[15])], limit=1).id,
            'lst_price': row_data[19],
            'categ_id': self.env['product.category'].search([('complete_name', '=', row_data[20])], limit=1).id,
            'available_in_pos': True,
            'last_excel_update': fields.Date.context_today(self),
            'uom_id': self.env['uom.uom'].search([('name', '=', str(row_data[22]))], limit=1).id,
        })

        if row_data[2]:
            return {
                'partner_ref': row_data[0],
                'date_order': row_data[1],
                'partner_id': self.env['res.partner'].search([('name', '=', row_data[2])],
                                                             limit=1).id,
                'user_id': self.env['res.users'].search([('name', '=', row_data[3])], limit=1).id,
                'currency_id': self.env['res.currency'].search([('name', '=', str(row_data[4]))], limit=1).id,
                'order_line': [(0, 0, {
                    'product_qty': float(row_data[5]),
                    'product_id': product.id,
                    'name': row_data[6],
                    'price_unit': row_data[7],
                    'date_planned': row_data[8],
                    'product_uom': self.env['uom.uom'].search([('name', '=', str(row_data[9]))], limit=1).id,
                })
                               ],
                'picking_type_id': self.env['stock.picking.type'].search([('display_name', '=', row_data[10])],
                                                                         limit=1).id,
                'is_excel_import': True,
            }
        else:
            return {
                'product_qty': float(row_data[5]),
                'product_id': product.id,
                'name': row_data[6],
                'price_unit': row_data[7],
                'date_planned': row_data[8],
                'product_uom': self.env['uom.uom'].search([('name', '=', str(row_data[9]))], limit=1).id,
            }

    def get_product(self, row):
        product = self.env['product.product'].search(['|', ('default_code', '=', row[12]), ('barcode', '=', row[11])],
                                                     limit=1)
        template = self.env['product.template'].search([('default_code', '=', row[13])], limit=1)
        color = row[16]
        sizes = row[17]
        gender = row[18]
        variants = {"Color": color, "Talla": sizes, "Genero": gender}
        values = json.dumps(variants, sort_keys=True)
        if not product or product.combination_names != values:
            if not template and not product:
                raise UserError(_("Error: No existe el producto padre con el codigo: %s" % row[13]))
            # check if the attribute exist
            if not template and product:
                template = product.product_tmpl_id

            if values not in template.product_variant_ids.mapped('combination_names'):
                for k, v in variants.items():
                    attribute_name = self.env['product.attribute'].search([('name', '=', k)], limit=1)
                    attribute_value = self.env['product.attribute'].search([('name', '=', k),
                                                                            ('value_ids.name', '=', v)], limit=1)
                    line = self.env['product.template.attribute.line'].with_context(is_created_excel=True).search(
                        [('product_tmpl_id', '=', template.id),
                         ('attribute_id', '=', attribute_name.id)])
                    if not attribute_value:
                        new_attribute = attribute_name.value_ids.create({'name': v, 'attribute_id': attribute_name.id})
                        line.write({'value_ids': [(4, new_attribute.id), ]})
                        continue
                    attribute = attribute_name.value_ids.filtered(lambda x: x.name == v)
                    if attribute not in line.value_ids:
                        line.write({'value_ids': [(4, attribute.id), ]})
            product = template.product_variant_ids.filtered(lambda x: x.combination_names == values)
        return product
