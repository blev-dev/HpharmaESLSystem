# -*- coding: utf-8 -*-
from odoo import models, fields, api
import json
import http.client
import logging
_logger = logging.getLogger(__name__)

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
    json_product_codes = fields.Text("json Codes-barres produits")
    product_names_scanned = fields.Text("Produits scannés")

    # Champ de scan standard
    scan_input = fields.Char("Scanner un code produit")
    full_pic_url = fields.Char("Template", compute="_compute_full_pic_url", store=False)

    @api.onchange('scan_input')
    def _onchange_scan_input(self):
        if not self.scan_input:
            return

        # 1. Recherche du produit
        product = self.env['product.product'].search([('barcode', '=', self.scan_input)], limit=1)
        
        # Reset immédiat du champ scan pour le prochain scan
        scan_val = self.scan_input
        self.scan_input = "" 

        if not product:
            return {
                'warning': {
                    'title': "Erreur",
                    'message': f"Produit inconnu : {scan_val}",
                    'type': 'warning'
                }
            }

        code_barre = product.barcode
        try:
            codes_list = json.loads(self.json_product_codes or "[]")
        except:
            codes_list = [""] * (self.item_num or 0)

        # 2. Vérification doublon
        if code_barre in codes_list:
             return {
                'warning': {
                    'title': "Déjà scanné",
                    'message': f"Le produit {code_barre} est déjà dans la liste.",
                    'type': 'warning'
                }
            }

        # 3. Remplissage de la liste
        try:
            idx = codes_list.index("")
            codes_list[idx] = code_barre
        except ValueError:
             return {
                'warning': {
                    'title': "Plein",
                    'message': "Tous les emplacements sont remplis.",
                    'type': 'warning'
                }
            }

        # 4. MISE A JOUR DES CHAMPS (Le plus important)
        self.json_product_codes = json.dumps(codes_list)
        
        # Mise à jour visuelle de la liste des noms
        names = []
        for code in codes_list:
            if code:
                p = self.env['product.product'].search([('barcode', '=', code)], limit=1)
                names.append(f"{code} - {p.display_name}" if p else f"{code}")
        self.product_names_scanned = '\n'.join(names)

        # 5. PAS DE RETURN D'ACTION !
        # Si vous voulez vraiment confirmer, utilisez un warning type 'info' 
        # ou laissez simplement l'utilisateur voir le champ 'Produits scannés' se mettre à jour.
        
        # Supprimez cette ligne : 
        # return self._notify(...) 
        
        # Utilisez ceci si vous voulez vraiment une popup bloquante :
        return {
            'warning': {
                'title': "Succès",
                'message': f"Produit ajouté : {product.display_name}",
                'type': 'notification' # Parfois 'notification' ne marche pas, utiliser 'warning' par défaut
            }
        }

    @api.onchange('esl_id_scan')
    def _onchange_esl_id_scan(self):
        self.action_multibind()

    def action_multibind(self):
        esl_record = self.env['esl.esl'].search([], limit=1)
        if not esl_record:
            return self._notify("❌ Aucune instance ESL trouvée.", notif_type="warning")
        esl_record.check_and_refresh_token()
        try:
            products = json.loads(self.json_product_codes or "[]")
            products = [p.strip() for p in products if p and p.strip()]
        except Exception as e:
            return self._notify(f"Erreur parsing json_product_codes : {str(e)}", notif_type="warning")

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
            'Authorization': esl_record.token or "",
            'Content-Type': 'application/json'
        }

        try:
            conn = http.client.HTTPSConnection("blev29.kalanda.info")
            conn.request("POST", "/api-esl/ZK_bindMultiESL", json.dumps(payload), headers)
            _logger.info("[Hpharma ESL] Envoi liaison multiple ESL: %s", payload)
            res = conn.getresponse()
            _logger.info("[Hpharma ESL] Réponse liaison multiple ESL status: %s", res.status)
            response_data = res.read().decode("utf-8")
            self.json_product_codes = json.dumps([""] * len(products))  # ["", "", ...]
            self.product_names_scanned = ""
            self.esl_id_scan = ""
            if res.status != 200:
                _logger.error("[Hpharma ESL] Erreur liaison multiple ESL : %s", response_data)
                raise Exception(f"Erreur API ({res.status}) : {response_data}")
            else:
                _logger.info("[Hpharma ESL] Liaison multiple ESL réussie : %s", response_data)
                

            #  Reset des champs après succès
            self.json_product_codes = json_product_codes = json.dumps([""] * self.item_num) 
            self.product_names_scanned = ""
            self.esl_id_scan = ""

            #  Reload de la page avec notification
            return {
                'type': 'ir.actions.client',
                'tag': 'reload',  # force le reload du formulaire / vue
                'params': {
                    'message': f"Produits liés à l'ESL avec succès.",
                }
            }

        except Exception as e:
            _logger.error(("[Hpharma ESL] Exception liaison multiple ESL : %s", str(e)))


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
        if record.item_num < 1:
            record.json_product_codes = json.dumps([])
        else:
            record.json_product_codes = json.dumps([""] * record.item_num)  # Initialise avec des chaînes vides
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