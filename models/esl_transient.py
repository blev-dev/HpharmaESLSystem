# -*- coding: utf-8 -*-
from odoo import models, fields, api
import json, http

class EslBind(models.TransientModel):
    _name = 'esl.bind'
    _description = 'Bind ESL'
    name = fields.Char(default="Bind ESL")
    code_1 = fields.Char(string="Produit")
    code_2 = fields.Char(string="ESL")
    product_name = fields.Char(string="Nom du produit", readonly=True)
    product_image = fields.Binary(string="Image du produit", readonly=True)

    @api.onchange('code_1')
    def _onchange_code_1(self):
        if not self.code_1:
            self.product_name = ''
            self.product_image = False
            return
        product = self.env['product.product'].search([('barcode', '=', self.code_1)], limit=1)
        if product:
            self.product_name = product.name
            self.product_image = product.image_128
        else:
            self.product_name = "Produit non trouvé"
            self.product_image = False
    
    @api.onchange('code_2')
    def _onchange_code_2(self):
        if self.code_2 and self.code_2.strip():
                self.action_bind()

    def action_bind(self):
        esl_record = self.env['esl.esl'].search([], limit=1)
        if not esl_record:
            { 'type': 'ir.actions.client', 'tag': 'reload',} # reload pour rafraîchir l'interface
            return self._notify("Aucune instance ESL trouvée.")
        esl_record.check_and_refresh_token()
        payload = json.dumps({
            "uniqueId": esl_record.unique_id,
            "StoreId": esl_record.StoreId,
            "product": self.code_1,
            "esl": self.code_2,
        })
        headers = {
            'Authorization': esl_record.token,
            'Content-Type': 'application/json'
        }

        try:
            import http.client
            conn = http.client.HTTPSConnection("blev29.kalanda.info")
            conn.request("POST", "/api-esl/ZK_bindSingleESL", payload, headers)
            res = conn.getresponse()
            response_data = res.read().decode("utf-8")

            if res.status != 200:
                raise Exception(f"Erreur API : {response_data}")

            new_wizard = self.env['esl.bind'].create({})
            # Vider les champs après succès
            self.code_1 = False
            self.code_2 = False
            self.product_name = False
            self.product_image = False
            { 'type': 'ir.actions.client', 'tag': 'reload',}
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'esl.bind',
                'view_mode': 'form',
                'res_id': new_wizard.id,
                'target': 'current',
                'effect': {
                    'fadeout': 'slow',
                    'message': "Produit {self.code_1} lié à ESL {self.code_2} avec succès ✅",
                    'type': 'rainbow_man',
                }
            }
        except Exception as e:
            { 'type': 'ir.actions.client', 'tag': 'reload',}
            return self._notify(str(e))

    def _notify(self, message):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'ESL',
                'message': message,
                'sticky': True,
                'timeout': 10000,
            }
        }
    
class EslUnbind(models.TransientModel):
    _name = 'esl.unbind'
    _description = 'Unbind ESL'
    name = fields.Char(default="Unbind ESL")
    code_1 = fields.Char(string="ESL")

    def action_unbind(self):
        esl_record = self.env['esl.esl'].search([], limit=1)
        esl_record.check_and_refresh_token()
        payload = json.dumps({
            "uniqueId": esl_record.unique_id,
            "StoreId": esl_record.StoreId,
            "esl": self.code_1,
        })
        headers = {
            'Authorization': esl_record.token,
            'Content-Type': 'application/json'
        }

        try:
            conn = http.client.HTTPSConnection("blev29.kalanda.info")
            conn.request("POST", "/api-esl/ZK_unbindESL", payload, headers)
            res = conn.getresponse()
            response_data = res.read().decode("utf-8")

            if res.status != 200:
                raise Exception(f"Erreur API : {response_data}")

            self.code_1 = False
            new_wizard = self.env['esl.unbind'].create({})
            { 'type': 'ir.actions.client', 'tag': 'reload',}
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'esl.unbind',
                'view_mode': 'form',
                'res_id': new_wizard.id,
                'target': 'current',
                'effect': {
                    'fadeout': 'slow',
                    'message': f"ESL {self.code_1} détaché avec succès ✅",
                    'type': 'rainbow_man',
                }
            }

        except Exception as e:
            { 'type': 'ir.actions.client', 'tag': 'reload',}
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Erreur',
                    'message': str(e),
                    'sticky': False,
                    'type': 'danger',
                }
            }
    
    @api.onchange('code_1')
    def _onchange_code_1(self):
        if self.code_2 and self.code_1.strip():
            self.action_unbind()

    def _notify(self, message):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'ESL',
                'message': message,
                'sticky': False,
                'timeout': 10000, 
            }
        }