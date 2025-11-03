# -*- coding: utf-8 -*-
from odoo import models, fields, api
import json

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
    product_codes = fields.Text("Codes-barres produits")

    # Champ de scan standard
    scan_input = fields.Char("Scanner un code produit")
    full_pic_url = fields.Char("Template", compute="_compute_full_pic_url", store=False)

    @api.depends("temp_pic_url")
    def _compute_full_pic_url(self):
        base_url = "https://esl.zkong.com/"
        for record in self:
            record.full_pic_url = f"{base_url}{record.temp_pic_url}" if record.temp_pic_url else False

    @api.model
    def create(self, vals):
        record = super().create(vals)
        if record.item_num and not record.product_codes:
            record.product_codes = json.dumps([""] * record.item_num)
        return record

    def write(self, vals):
        res = super().write(vals)
        for record in self:
            if "item_num" in vals:
                codes = json.loads(record.product_codes or "[]")
                diff = record.item_num - len(codes)
                if diff > 0:
                    codes.extend([""] * diff)
                elif diff < 0:
                    codes = codes[:record.item_num]
                super(EslTemplate, record).write({'product_codes': json.dumps(codes)})
        return res
    
    def action_add_scan(self):
        for record in self:
            code = (record.scan_input or "").strip()
            if not code:
                continue

            # Charger la liste actuelle
            try:
                codes = json.loads(record.product_codes or "[]")
            except Exception:
                codes = []

            # Vérifier doublon
            if code in codes:
                record.scan_input = ""
                return self._notify(f"Le code {code} est déjà présent.", "warning")

            # Chercher le produit
            product = self.env['product.product'].search([('barcode', '=', code)], limit=1)
            if product:
                codes.append(code)
                # Limiter à item_num
                if record.item_num and len(codes) > record.item_num:
                    codes = codes[:record.item_num]
                # ⚡ Écrire le JSON mis à jour
                record.product_codes = codes
                record.write({'product_codes': json.dumps(codes)})
                message = f"Produit trouvé : {product.name} ({len(codes)}/{record.item_num})"
                notif_type = "success"
            else:
                message = f"Produit non trouvé pour le code : {code}"
                notif_type = "warning"

            record.scan_input = ""
            return self._notify(message, notif_type)


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
