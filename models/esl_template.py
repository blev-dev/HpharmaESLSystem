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
        if not product:
            return {
                'warning': {
                    'title': "Avertissement",
                    'message': f"Aucun produit trouvé pour le code-barres : {self.scan_input}",
                    'type': 'warning'
                }
            }

        code_barre = product.barcode
        codes_list = json.loads(self.Json_product_codes or "[]")

        # Vérifie doublon
        if code_barre in codes_list:
            return {
                'warning': {
                    'title': "Doublon",
                    'message': f"Le code-barres {code_barre} est déjà dans la liste.",
                    'type': 'danger'
                }
            }

        # Remplit la première case vide
        try:
            idx = codes_list.index("")
            codes_list[idx] = code_barre
            self.Json_product_codes = json.dumps(codes_list)
            self.scan_input = ""
        except ValueError:
            return {
                'warning': {
                    'title': "Liste pleine",
                    'message': "Tous les emplacements sont déjà remplis.",
                    'type': 'warning'
                }
            }

        # Met à jour la liste des noms produits scannés
        names = []
        for code in codes_list:
            if code:
                prod = self.env['product.product'].search([('barcode', '=', code)], limit=1)
                names.append(f"{code} - {prod.display_name}" if prod else f"{code} - [Inconnu]")
        self.product_names_scanned = '\n'.join(names)
        self.env['esl.template'].browse(self.id).write({'Json_product_codes': self.Json_product_codes})
        return self._notify(
            f"Scan réussi : {product.display_name} ({product.barcode})\n"
            f"Etat actuel des codes : {self.Json_product_codes}",
            notif_type="success"
        )

    @api.onchange('esl_id_scan')
    def _onchange_esl_id_scan(self):
        self.action_multibind()

    def action_multibind(self):
        esl_record = self.env['esl.esl'].search([], limit=1)
        if not esl_record:
            return self._notify("❌ Aucune instance ESL trouvée.", notif_type="warning")

        try:
            products = json.loads(self.Json_product_codes or "[]")
            products = [p.strip() for p in products if p and p.strip()]
        except Exception as e:
            return self._notify(f"Erreur parsing Json_product_codes : {str(e)}", notif_type="warning")

        if not products:
            return self._notify(
                f"⚠️ Aucun code produit à envoyer.\n"
                f"Contenu actuel de Json_product_codes : {self.product_names_scanned} : {self.Json_product_codes}",
                notif_type="warning"
            )

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
            self.Json_product_codes = json.dumps([""] * len(products))  # ["", "", ...]
            self.product_names_scanned = ""
            self.esl_id_scan = ""
            if res.status != 200:
                raise Exception(f"Erreur API ({res.status}) : {response_data}")

            # ✅ Reset des champs après succès
            self.Json_product_codes = json.dumps([""] * len(products))
            self.product_names_scanned = ""
            self.esl_id_scan = ""

            # 🔄 Reload de la page avec notification
            return {
                'type': 'ir.actions.client',
                'tag': 'reload',  # force le reload du formulaire / vue
                'params': {
                    'message': f"Produits liés à l'ESL avec succès.\nPayload envoyé : {json.dumps(payload)}",
                }
            }

        except Exception as e:
            msg = f"❌ Erreur : {str(e)}\n\nPayload : {json.dumps(payload, indent=2)}\n\nHeaders : {headers}"
            return self._notify(msg, notif_type="danger")


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
