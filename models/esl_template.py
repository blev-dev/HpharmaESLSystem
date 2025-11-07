# -*- coding: utf-8 -*-
from odoo import models, fields, api
import json
import http.client

class EslTemplate(models.Model):
    _name = "esl.template"
    _description = "Template ESL"

    esl_id = fields.Char("ID ESL", required=True, index=True)
    template_number = fields.Char("Template Number")
    name = fields.Char("Template Name")
    size = fields.Char("Taille")
    resolution = fields.Char("Résolution")
    hardware_str = fields.Char("Couleur / Hardware")
    item_num = fields.Integer("Nombre de produits")
    temp_pic_url = fields.Char("URL image (partielle)")
    is_enable = fields.Boolean("Actif", default=True)
    json_raw = fields.Text("JSON brut")

    esl_id_scan = fields.Char("Code ESL")
    Json_product_codes = fields.Text("json Codes-barres produits")
    product_names_scanned = fields.Text("Produits scannés")

    # Champ de scan standard
    scan_input = fields.Char("Scanner un code produit")
    full_pic_url = fields.Char("Template", compute="_compute_full_pic_url", store=False)

    @api.onchange('scan_input')
    def _onchange_scan_input(self):
        if not self.scan_input:
            return

        # Cherche le produit via son code-barres
        product = self.env['product.product'].search([('barcode', '=', self.scan_input)], limit=1)
        if product:
            code_barre = product.barcode
            Json_product_codes = json.loads(self.Json_product_codes or "[]")

            # Vérifie doublon
            if code_barre in Json_product_codes:
                return {
                    'warning': {
                        'title': "Doublon",
                        'message': f"Le code-barres {code_barre} est déjà dans la liste.",
                        'type': 'danger'
                    }
                }

            # Remplit la première case vide
            try:
                idx = Json_product_codes.index("")
                Json_product_codes[idx] = code_barre
                self.Json_product_codes = json.dumps(Json_product_codes)
                self.scan_input = ""
            except ValueError:
                # S'il n'y a plus de case vide, on n'ajoute pas
                return {
                    'warning': {
                        'title': "Liste pleine",
                        'message': "Tous les emplacements sont déjà remplis.",
                        'type': 'warning'
                    }
                }

            # Met à jour la liste des noms produits scannés
            names = []
            for code in Json_product_codes:
                if code:
                    prod = self.env['product.product'].search([('barcode', '=', code)], limit=1)
                    if prod:
                        names.append(f"{code} - {prod.display_name}")
                    else:
                        names.append(f"{code} - [Inconnu]")
            self.product_names_scanned = '\n'.join(names)

            return {
                'warning': {
                    'title': "Scan réussi",
                    'message': f"Produit trouvé : {product.display_name} ({product.barcode})",
                    'type': 'success'
                }
            }
        else:
            return {
                'warning': {
                    'title': "Avertissement",
                    'message': f"Aucun produit trouvé pour le code-barres : {self.scan_input}",
                    'type': 'warning'
                }
            }

    @api.onchange('esl_id_scan')
    def _onchange_esl_id_scan(self):
        self.action_multibind()

    def action_multibind(self):
        # Recherche d’une configuration ESL existante
        esl_record = self.env['esl.esl'].search([], limit=1)
        if not esl_record:
            return self._notify("❌ Aucune instance ESL trouvée.", reload=True)

        # Prépare la liste des produits
        try:
            products = json.loads(self.Json_product_codes or "[]")
            products = [p for p in products if p]
        except Exception:
            products = []

        if not products:
            return self._notify("⚠️ Aucun code produit à envoyer.", reload=True)

        # Construction du payload JSON
        payload = {
            "uniqueId": esl_record.unique_id,
            "storeId": esl_record.StoreId,
            "templateId": str(self.esl_id),
            "esl": str(self.esl_id_scan or ""),
            "data": {"products": products},
            "debug": False
        }

        headers = {
            'ZKAuthorization': esl_record.zk_token or "",
            'Authorization': esl_record.token or "",
            'Content-Type': 'application/json'
        }

        try:
            conn = http.client.HTTPSConnection("blev29.kalanda.info")
            conn.request("POST", "/api-esl/ZK_bindMultiESL", json.dumps(payload), headers)
            res = conn.getresponse()
            response_data = res.read().decode("utf-8")

            if res.status != 200:
                raise Exception(f"Erreur API ({res.status}) : {response_data}")

            # Succès ✅
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': "Succès ✅",
                    'message': "Produits liés à l'ESL avec succès.",
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            msg = f"❌ Erreur : {str(e)}\n\nPayload : {json.dumps(payload, indent=2)}\n\nHeaders : {headers}"
            return self._notify(msg, reload=True)

    def _notify(self, message):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'ESL',
                'message': message,
                'sticky': True,
                'timeout': 100000,
            }
        }
    
    @api.depends("temp_pic_url")
    def _compute_full_pic_url(self):
        base_url = "https://esl.zkong.com/"
        for record in self:
            record.full_pic_url = f"{base_url}{record.temp_pic_url}" if record.temp_pic_url else False

    @api.model
    def create(self, vals):
        record = super().create(vals)
        if record.item_num and not record.Json_product_codes:
            record.Json_product_codes = ""
        return record

    def write(self, vals):
        res = super().write(vals)
        for record in self:
            if "item_num" in vals:
                codes = json.loads(record.Json_product_codes or "[]")
                diff = record.item_num - len(codes)
                if diff > 0:
                    codes.extend([""] * diff)
                elif diff < 0:
                    codes = codes[:record.item_num]
                super(EslTemplate, record).write({'Json_product_codes': json.dumps(codes)})
        return res

    def _notify(self, message, notif_type="info"):
        """
        Retourne un dictionnaire pour afficher une notification Odoo
        """
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'ESL Scan',
                'message': message,
                'type': notif_type,
                'sticky': False,
                'timeout': 5000,
            }
        }
