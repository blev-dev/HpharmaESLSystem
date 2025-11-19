from odoo import models, fields, api
import requests, base64, json, http, os
from odoo.exceptions import ValidationError
from odoo.exceptions import UserError
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import padding
from odoo.tools import config
from datetime import timedelta
# --------------------------
# Cache global des stores test git
# --------------------------
import logging
_logger = logging.getLogger(__name__)
_cached_stores_global = []

class Esl(models.Model):
    """
    Modèle principal pour la connexion et la synchronisation avec les ESL Hpharma.

    Gère :
    - Connexion via API ESL
    - Récupération des templates
    - Envoi des produits
    - Gestion des tâches planifiées (cron)
    """
    _name = "esl.esl"
    _description = "Hpharma ESL Connection"
    name = fields.Char(default="Paramètres ESL")
    user_lang = fields.Char("Langue utilisateur", readonly=True)

    login = fields.Char("Login", required=True)
    password = fields.Char("Password", required=True)
    token = fields.Char("Token")
    token_expiration = fields.Datetime("Token Expiration", readonly=True)
    publickey = fields.Text("Public Key")
    doi = fields.Datetime("Date of last import", readonly=True, default=lambda self: fields.Datetime.now())
    labeltype = fields.Selection(
        [
            ("zkong", "Zkong"),
            ("psl", "PSL"),
            ("pricer", "Pricer"),
        ],
        string="Type d'étiquette",
        default="zkong",
        required=True,
    )
    state = fields.Selection([
        ('disconnected', 'Disconnected'),
        ('connected', 'Connected'),
        ('error', 'Error')
    ], string="Status", default="disconnected")
    unique_id = fields.Char("Unique ID", required=True)
    agency_id = fields.Char("agency_id", readonly=True)
    merchant_id = fields.Char("merchant_id", readonly=True)
    interval_number = fields.Integer("Intervalle", default=1)
    interval_type = fields.Selection([
        ('hours', 'Heures'),
        ('days', 'Jours'),
    ], string="Type d'intervalle", default='hours')
    cron_active = fields.Boolean("Activer la planification", default=False)
    product_batch = fields.Integer("lots de produits envoyées", default=10)
    url_sendItem = fields.Char("url send items")
    StoreId = fields.Selection(selection=lambda self: self._get_store_selection(), string="Store ID")

    # -------------------------------------------------------------
    #                      MÉTHODES DE BASE
    # -------------------------------------------------------------

    @api.model
    def create(self, vals):
        """
        Surcharge de la création d'un ESL.
        Vérifie qu'il n'existe qu'une seule instance et configure le cron.

        Paramètres:
            vals (dict): valeurs du nouvel enregistrement

        Retour:
            record (recordset): l'enregistrement créé
        """
        if self.search_count([]) >= 1:
            raise ValidationError("Une seule instance de connexion est autorisée.")
        
        record = super().create(vals)
        cron = self.env.ref('module_HpharmaESLSystem.ir_cron_auto_send_products', raise_if_not_found=False)
        if cron:
            cron.write({
                'interval_number': vals.get('interval_number', 1),
                'interval_type': vals.get('interval_type', 'hours'),
            })
        return record

    def write(self, vals):
        """
        Surcharge de la mise à jour d'un ESL.
        Met à jour le cron si l'intervalle change.

        Paramètres:
            vals (dict): valeurs à mettre à jour

        Retour:
            bool: succès de la mise à jour
        """
        vals['user_lang'] = self.env.user.lang

        res = super().write(vals)
        if 'interval_number' in vals or 'interval_type' in vals:
            self.update_cron_schedule()
        return res

    @staticmethod
    def format_price(value):
        """
        Formate un prix avec deux décimales, retourne int si entier.

        Paramètres:
            value (float): valeur du prix

        Retour:
            float | int: prix formaté
        """
        value = round(value or 0.0, 2)
        if value.is_integer():
            return int(value)
        return value

    # -------------------------------------------------------------
    #                   CONSTRUCTION DES PRODUITS
    # -------------------------------------------------------------
    def build_product_json(self, logs):
        """
        Construit la structure JSON des produits pour l'envoi à l'ESL.

        Paramètres:
            logs (list): liste pour collecter les logs d'exécution

        Retour:
            dict: structure JSON complète pour l'envoi
        """
        products = self.env['product.product'].search([])
        item_list = []

        for p in products:
            barcode_value = p.barcode or str(p.default_code)
            item = {
                "attrCategory": "default",
                "attrName": "default",
                "barCode": barcode_value,
                "itemTitle": p.name or "",
                "shortTitle": "",
                "classLevel": "",
                "originalPrice": self.format_price(p.list_price),
                "price": self.format_price(p.list_price),
                "qrCode": "",
                "nfcUrl": "",
                "productArea": "",
                "productCode": p.default_code or "",
                "productSku": "",
                "promotionText": "",
                "label": "",
                "stock1": getattr(p, "qty_available", 0.0),
                "stock2": 0,
                "stock3": 0,
                **{f"custFeature{i}": "" for i in range(1, 21)},
            }
            item_list.append(item)

        return {
            "uniqueId": self.unique_id,
            "agencyId": self.agency_id,
            "merchantId": self.merchant_id,
            "itemList": item_list
        }
    
    # -------------------------------------------------------------
    #               GESTION ET RAFRAÎCHHISSEMENT TOKEN
    # -------------------------------------------------------------
    def check_and_refresh_token(self):
        now = fields.Datetime.now()
        # Si pas de token ou pas d'expiration → on reconnecte
        if not self.api_token or not self.token_expiration:
            self.connectesl()
            _logger.info("[Hpharma ESL] Token absent, connexion effectuée.")
            return self.api_token

        # Token expiré ?
        if self.token_expiration < now:
            _logger.info("[Hpharma ESL] Token expiré, reconnexion en cours.")
            return self.connectesl()


    # -------------------------------------------------------------
    #                      CONNEXION ESL
    # -------------------------------------------------------------
    def connectesl(self):
        """
        Connecte à l'ESL Hpharma et récupère le token, agency_id et merchant_id.

        Retour:
            dict: notification Odoo pour informer du succès ou de l'erreur
        """
        self.ensure_one()
        self.token = ""
        logs = []

        # Étape 1 : clé publique
        try:
            response = requests.get("https://blev29.kalanda.info/api-esl/getPublicKey", timeout=10)
            if response.status_code != 200:
                self.state = "error"
                return self._notify(f"❌ Erreur récupération clé publique (HTTP {response.status_code})")
            content = response.text.strip()
            self.publickey = content
        except Exception as e:
            self.state = "error"
            return self._notify(f"❌ Exception clé publique : {str(e)}")

        if not content or "-----BEGIN" not in content:
            self.state = "error"
            return self._notify("❌ Clé publique invalide reçue.")

        if not self.login or not self.password:
            self.state = "error"
            return self._notify("❌ Identifiants ESL manquants.")

        # Étape 2 : demande de token
        try:
            public_key = serialization.load_pem_public_key(content.encode("utf-8"), backend=default_backend())
            encrypted = public_key.encrypt(self.password.encode("utf-8"), padding.PKCS1v15())
            encrypted_b64 = base64.b64encode(encrypted).decode("utf-8")

            payload = {"mode": "CLOUD", "username": self.login, "password": encrypted_b64, "UniqueId": self.unique_id , "enableZkong": True}
            response_token = requests.post("https://blev29.kalanda.info/api-esl/getToken", json=payload, timeout=30)
            _logger.info("[Hpharma ESL] Response getToken: %s", response_token.text)
            if response_token.status_code != 200:
                self.state = "error"
                return self._notify(f"❌ Erreur token (HTTP {response_token.status_code})")
            
            token_json = response_token.json()
            self.token = token_json.get("data", {}).get("token", "")
            self.agency_id = token_json.get("data", {}).get("agencyId", "NA")
            self.merchant_id = token_json.get("data", {}).get("merchantId", "NA")
            self.token_expiration = fields.Datetime.now() + timedelta(hours=2)

        except Exception as e:
            self.state = "error"
            _logger.error("[Hpharma ESL] Erreur getToken: %s", str(e))
            return self._notify(f"❌ Erreur getToken : {str(e)}")

        self.state = "connected"
        _logger.info("[Hpharma ESL] Connexion ESL réussie pour %s", self.login)
        return self._notify("✅ Connexion ESL Hpharma réussie.")

    # -------------------------------------------------------------
    #                  ENVOI DES PRODUITS
    # -------------------------------------------------------------
    def importesl(self):
        """
        Envoie les produits batch par batch vers l'ESL.

        Retour:
            dict: notification Odoo avec le nombre de produits envoyés
        """
        self.ensure_one()
        logs = []
        all_products_payload = self.build_product_json(logs)
        all_items = all_products_payload.get("itemList", [])

        if not all_items:
            return self._notify("⚠️ Aucun produit à envoyer.")

        batch_size = self.product_batch or 19999
        total_sent = 0
        response_data = ""
        response_json = {}

        for i in range(0, len(all_items), batch_size):
            batch_items = all_items[i:i + batch_size]

            payload_dict = {
                "uniqueId": self.unique_id,
                "agencyId": self.agency_id,
                "merchantId": self.merchant_id,
                "itemList": batch_items,
                "token": self.token
            }
            payload = json.dumps(payload_dict)

            headers = {
                'Authorization': self.token,
                'Content-Type': 'application/json'
            }

            try:
                conn = http.client.HTTPSConnection("blev29.kalanda.info")
                conn.request("POST", "/api-esl/ZK_sendItem", payload, headers)
                res = conn.getresponse()
                response_data = res.read().decode("utf-8")

                try:
                    response_json = json.loads(response_data)
                except Exception:
                    _logger.error("[Hpharma ESL] Erreur parsing JSON response: %s", response_data)
                    response_json = {}
                _logger.info("[Hpharma ESL] Response sendItem: %s", response_data)
                if res.status == 200:
                    self.state = "connected"
                    self.doi = fields.Datetime.now()
                    _logger.info("[Hpharma ESL] Batch de %d produits envoyé avec succès.", len(batch_items))
                else:
                    self.state = "error"
                    _logger.error("[Hpharma ESL] Erreur API sendItem (HTTP %d): %s", res.status, response_data)

            except Exception as e:
                self.state = "error"
                response_data = str(e)
                response_json = {}
                _logger.error("[Hpharma ESL] Exception envoi produits: %s", response_data)

            total_sent += len(batch_items)

            # 🔒 Masquer les tokens si ajout au log
            safe_payload_dict = dict(payload_dict)
            safe_payload_dict["token"] = "****"
            safe_payload_dict["zk"] = "****"
            logs.append(json.dumps(safe_payload_dict, indent=4, ensure_ascii=False))
        return self._notify(
            f"✅ Produits envoyés : {total_sent}\n"
            f"Réponse : {response_json.get('message', response_data)}"
        )

    # -------------------------------------------------------------
    #                 RÉCUPÉRATION DES STORE IDS
    # -------------------------------------------------------------
    def getstoreid(self):
        self.ensure_one()
        global _cached_stores_global
        _cached_stores_global = []  # on vide à chaque appel

        payload = json.dumps({
            "uniqueId": self.unique_id,
            "agencyId": self.agency_id,
            "merchantId": self.merchant_id,
        })

        headers = {
            'Authorization': self.token or "",
            'Content-Type': 'application/json'
        }

        try:
            conn = http.client.HTTPSConnection("blev29.kalanda.info")
            conn.request("POST", "/api-esl/ZK_getStoreId", payload, headers)
            res = conn.getresponse()
            response_data = res.read().decode("utf-8")
            _logger.info("[Hpharma ESL] Response getStoreId: %s", response_data)
            if res.status != 200:
                return self._notify(f"Erreur API : {response_data}")

            response_json = json.loads(response_data)
            store_data = response_json.get("data", [])

            if not store_data:
                return self._notify("⚠️ Aucun store trouvé sur l’API.")

            stores = []
            for store in store_data:
                store_id = str(store.get("storeId"))
                store_name = store.get("storeName", store_id)
                stores.append((store_id, store_name))

            _cached_stores_global = stores
            if stores:
                self.StoreId = stores[0][0]

            self._notify(f"✅ {len(stores)} stores récupérés.")
            return {'type': 'ir.actions.client', 'tag': 'reload'}

        except Exception as e:
            return self._notify(f"❌ Erreur lors de la récupération : {e}")

    # -------------------------------------------------------------
    #                 OUTILS DE SÉLECTION STORE
    # -------------------------------------------------------------
    def _get_store_selection(self):
        """Retourne la liste des stores stockés globalement."""
        global _cached_stores_global
        return _cached_stores_global
    
    # -------------------------------------------------------------
    #                  CRON & NOTIFICATIONS
    # -------------------------------------------------------------
    def auto_send_products(self):
        _logger.info("[Hpharma ESL] Démarrage du CRON d'envoi automatique des produits.")
        for record in self.search([]):
            try:
                lang = record.user_lang or 'fr_BE'
                record = record.with_context(lang=lang)
                record.connectesl()
                record.importesl()
            except Exception as e:
                record.state = "error"
                _logger.error("[Hpharma ESL] Erreur CRON envoi automatique: %s", str(e))
                record._notify(f"Erreur CRON envoi automatique : {str(e)}")
    # -------------------------------------------------------------
    #                      NOTIFICATIONS
    # -------------------------------------------------------------
    def _notify(self, message):
        """
        Retourne un dictionnaire pour afficher une notification dans Odoo.

        Paramètres:
            message (str): message à afficher

        Retour:
            dict: action Odoo notification
        """
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
    # -------------------------------------------------------------
    #                  GESTION DU CRON
    # -------------------------------------------------------------
    def action_update_cron(self):
        self.ensure_one()
        cron = self.env.ref('module_HpharmaESLSystem.ir_cron_auto_send_products', raise_if_not_found=False)
        if cron:
            cron.sudo().write({
                'interval_number': int(self.interval_number or 1),
                'interval_type': self.interval_type if self.interval_type in ['minutes', 'hours', 'days'] else 'hours',
                'active': self.cron_active,
            })
            message = f"⏱ Intervalle de la tâche planifiée mis à jour : {self.interval_number} {self.interval_type}"
        else:
            message = "⚠️ CRON non trouvé"
        return self._notify(message)
    # -------------------------------------------------------------
    #                  MISE À JOUR DU CRON
    # -------------------------------------------------------------
    def update_cron_schedule(self):
        self.ensure_one()
        cron = self.env.ref('module_HpharmaESLSystem.ir_cron_auto_send_products', raise_if_not_found=False)
        if cron:
            cron.sudo().write({
                'interval_number': int(self.interval_number or 1),
                'interval_type': self.interval_type if self.interval_type in ['minutes', 'hours', 'days'] else 'hours',
                'active': self.cron_active,
            })
    # -----------------------------------------------------------------
    #                      SYNCHRONISATION TEMPLATE ESL
    # -----------------------------------------------------------------

    def sync_templates_from_esl(self, esl_record=None):
        """
        Synchronise les templates depuis l'ESL.

        Paramètres:
            esl_record (recordset): instance ESL, optionnelle

        Retour:
            dict: notification Odoo du résultat de la synchronisation
        """
        # Récupère les templates via API pour cet ESL et crée/maj les enregistrements. #

        self = esl_record or self
        if not self.unique_id or not self.merchant_id:
            _logger.error("[Hpharma ESL] unique_id ou merchant_id manquants pour récupérer les templates.")
            return self._notify("❌ unique_id ou merchant_id manquants pour récupérer les templates")

        payload = {
            "uniqueId": self.unique_id,
            "agencyId": self.agency_id,
            "merchantId": self.merchant_id,
            "data": {"storeId": self.StoreId, "HardwareType": 3}
        }
        headers = {
            "Authorization": self.token or "",
            "Content-Type": "application/json",
        }

        try:
            resp = requests.post(
                "https://blev29.kalanda.info/api-esl/ZK_getTemplate",
                json=payload,
                headers=headers,
                timeout=30
            )
            resp.raise_for_status()
            _logger.info("[Hpharma ESL] Requête templates réussie: %s", resp.text)
        except Exception as e:
            _logger.error("[Hpharma ESL] Erreur requête templates: %s", str(e))
            return self._notify(f"❌ Erreur requête templates: {e}")


        try:
            data = resp.json()
        except Exception as e:
            _logger.error("[Hpharma ESL] Réponse templates non JSON: %s", str(e))
            return self._notify(f"❌ Réponse templates non JSON: {e}")

        # Correction: gérer le cas où la réponse est une liste ou un dict, avec log
        logs = []
        logs.append(f"Type de data reçu: {type(data)}")
        _logger.info("[Hpharma ESL] Type de data reçu pour templates: %s", type(data))
        if isinstance(data, list):
            content = data
        elif isinstance(data, dict):
            # data peut être directement la liste de templates ou un dict avec 'data' ou 'content'
            if "content" in data:
                content = data.get("content", [])
            elif "data" in data and isinstance(data["data"], list):
                content = data["data"]
            elif "data" in data and isinstance(data["data"], dict):
                content = data["data"].get("content", [])
            else:
                content = []
        else:
            content = []
        if not content:
            _logger.error(f"Contenu vide ou non trouvé. data: {data}")
            return self._notify("⚠️ Pas de template reçu.")

        Template = self.env['esl.template'].sudo()
        created = updated = 0

        for tmpl in content:
            _logger.debug("[Hpharma ESL] Traitement template: %s", tmpl)
            esl_id = str(tmpl.get("id") or tmpl.get("templateNumber") or "")
            # Conversion correcte en booléen
            is_enable_value = tmpl.get("isEnable", False)
            if isinstance(is_enable_value, str):
                is_enable_value = is_enable_value.strip().lower() in ["1", "true", "yes"]
            else:
                is_enable_value = bool(is_enable_value)

            vals = {
                "esl_id": esl_id,
                "template_number": tmpl.get("templateNumber"),
                "name": tmpl.get("templateName"),
                "size": tmpl.get("size"),
                "resolution": tmpl.get("resolution"),
                "hardware_str": tmpl.get("hardwareStr"),
                "item_num": tmpl.get("itemNum"),
                "temp_pic_url": tmpl.get("tempPicUrl"),
                "is_enable": is_enable_value,
                "json_raw": json.dumps(tmpl, ensure_ascii=False),
                "json_product_codes": json.dumps([""] * (tmpl.get("itemNum") or 0)),
            }
            _logger.debug("[Hpharma ESL] Traitement template ESL ID %s, is_enable: %s", esl_id, is_enable_value)
            existing = Template.search([("esl_id", "=", esl_id)], limit=1)
            if not is_enable_value:
                # Si désactivé, supprimer si existe
                if existing:
                    existing.unlink()
                    updated += 1
                continue
            # Si activé, créer ou mettre à jour
            _logger.debug("[Hpharma ESL] Création/Mise à jour template ESL ID %s", esl_id)
            if existing:
                existing.write(vals)
                updated += 1
            else:
                Template.create(vals)
                created += 1

        return self._notify(f"Templates synchronisés ✅ Créés: {created} — Mis à jour: {updated}")

    # -------------------------------------------------------------
    #                      OUTILS DIVERS        
    # -------------------------------------------------------------
    def FirstConnectionESL(self):
        for record in self.search([]):
            try:
                record.connectesl()
                record.getstoreid()
                record.sync_templates_from_esl()
                return { 'type': 'ir.actions.client', 'tag': 'reload',}
            except Exception as e:
                record.state = "error"
                record._notify(f"Erreur Connexion : {str(e)}")
                _logger.error("[Hpharma ESL] Erreur FirstConnectionESL: %s", str(e))
    # -------------------------------------------------------------
    #               TÉLÉCHARGEMENT LOG ODOO
    # -------------------------------------------------------------
    def download_odoo_log(self):
        # Chemin du fichier log depuis la configuration active
        log_path = config['logfile']  # récupère directement depuis Odoo

        if not log_path:
            raise UserError("Le fichier odoo.log n'est pas configuré dans Odoo (`logfile`).")

        if not os.path.exists(log_path):
            raise UserError(f"Le fichier odoo.log est introuvable à : {log_path}")

        # Lire le contenu
        with open(log_path, 'rb') as f:
            log_data = f.read()

        # Créer un attachment temporaire
        attachment = self.env['ir.attachment'].create({
            'name': 'odoo.log',
            'type': 'binary',
            'datas': base64.b64encode(log_data),
            'mimetype': 'text/plain',
            'res_model': self._name,
            'res_id': self.id or 0,
        })

        # Action de téléchargement
        return {
            'type': 'ir.actions.act_url',
            'url': f"/web/content/{attachment.id}?download=true",
            'target': 'self',
        }