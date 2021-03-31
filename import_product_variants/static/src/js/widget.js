/* Global jscolor */
odoo.define('import_product_variants.tree', function (require) {
"use strict";
    var core = require('web.core');
    var KanbanController = require('web.KanbanController');
    var KanbanView = require('web.KanbanView');
    var ListController = require('web.ListController');
    var ListView = require('web.ListView');
    var viewRegistry = require('web.view_registry');
    var QWeb = core.qweb;

    var ImportListController = ListController.extend({

        renderButtons: function () {
            this._super.apply(this, arguments);
            var self = this;
            if (self.modelName == 'purchase.order'){
                this.$buttons.append($(QWeb.render("ImportProductVariants.purchase_button", this)));
                this.$buttons.on('click', '.o_button_upload_variants', function () {
                console.log(self);
                return self._rpc({
                    model: 'purchase.order',
                    method: 'open_purchase_import_wizard',
                    args: [],
                }).then(function (results) {
                    self.do_action(results);
                });
            });
            }

            if (self.modelName == 'product.product'){
                this.$buttons.append($(QWeb.render("ImportProductVariants.purchase_button", this)));
                this.$buttons.on('click', '.o_button_upload_variants', function () {
                console.log(self);
                return self._rpc({
                    model: 'product.product',
                    method: 'open_product_import_wizard',
                    args: [],
                }).then(function (results) {
                    self.do_action(results);
                });
            });
            }

        },
    });

    var ImportListView = ListView.include({
        config: _.extend({}, ListView.prototype.config, {
            Controller: ImportListController,
        }),
    });


    viewRegistry.add('import_product_variants', ImportListView);

});

