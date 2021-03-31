import xlrd
import base64
import io
import datetime
import json
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import config, DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, pycompat


class ProductProductImport(models.TransientModel):
    _name = 'product.product.import.variants'
    _description = "Wizard to import product variants in custom layout excel"

    name = fields.Char("Import Name", compute="_get_import_name")
    excel_file = fields.Binary(string="Excel to Import", )
    excel_filename = fields.Char(string="FileName")
    include_title = fields.Boolean(string="Include Column Title", default=1)
    include_variants = fields.Boolean(string="In?")

    @api.depends('excel_filename')
    def _get_import_name(self):
        for record in self:
            record.name = record.excel_filename or "Not defined"

    def validate_excel(self):
        if not self.excel_file:
            raise UserError(_("Error: No hay un archivo adjuntado al campo de Series Xls file"))
        if '.xls' not in self.excel_filename:
            raise UserError(_("Error: El archivo no es .xls o xlsx"))

    def action_import_products(self):
        self.validate_excel()
        inputx = io.BytesIO()
        inputx.write(base64.decodebytes(self.excel_file))
        book = xlrd.open_workbook(file_contents=inputx.getvalue() or b'')
        rows = [val for val in self._read_xls_book(book)]
        if not rows:
            return False
        if self.include_title:
            rows = rows[1:]
        for row in rows:
            product = self.get_product(row)
            product.write({
                'barcode': row[0],
                'default_code': row[1],
                'name': row[3],
                'product_brand_id': self.env['product.brand'].search([('name', '=', row[4])], limit=1).id,
                'lst_price': row[8],
                'categ_id': self.env['product.category'].search([('complete_name', '=', row[9])], limit=1).id,
                'available_in_pos': True,
                'last_excel_update': fields.Date.context_today(self)
            })

    def get_product(self, row):
        product = self.env['product.product'].search(['|', ('default_code', '=', row[1]), ('barcode', '=', row[0])],
                                                     limit=1)
        template = self.env['product.template'].search([('default_code', '=', row[2])], limit=1)
        color = row[5]
        sizes = row[6]
        gender = row[7]
        variants = {"Color": color, "Talla": sizes, "Genero": gender}
        values = json.dumps(variants, sort_keys=True)
        if not product or product.combination_names != values:
            if not template and not product:
                raise UserError(_("Error: No existe el producto padre con el codigo: %s" % row[2]))
            # check if the attribute exist
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
                        line.write({'value_ids': [(4, new_attribute.id),]})
                        continue
                    attribute = attribute_name.value_ids.filtered(lambda x: x.name == v)
                    if attribute not in line.value_ids:
                        line.write({'value_ids': [(4, attribute.id), ]})
            product = template.product_variant_ids.filtered(lambda x: x.combination_names == values)
        return product

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
