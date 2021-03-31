
{
    'name': "Purchase product variant Import",
    'category': "web",
    'version': "13.0.1.0.0",
    "author": "OdooComunidad",
    'website': '',
    'depends': ['web','base','purchase'],
    'data': [
        'views/template.xml',
        'views/purchase_order_import_variants.xml',
        'views/product_product_import_variants.xml'
    ],
    'qweb': [
        'static/src/xml/templates.xml',
    ],
    'license': 'AGPL-3',
    'auto_install': False,
    'installable': True,
}
