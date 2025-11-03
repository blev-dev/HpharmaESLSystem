# Module Hpharma ESL System

## Présentation

Le module **Hpharma ESL System** permet de gérer les **étiquettes électroniques (ESL)** pour les pharmacies utilisant Odoo.  
Il offre la connexion avec les ESL, l’envoi automatique des produits, la synchronisation des templates et la liaison/déliaison des ESL avec les produits.

---

## Fonctionnalités

- Connexion sécurisée aux ESL Hpharma via API externe.
- Envoi automatique des produits vers les ESL (planification via cron).
- Synchronisation des templates d’étiquettes ESL.
- Liaison (`bind`) et déliaison (`unbind`) des ESL avec les produits.
- Gestion des droits d’accès pour administrateurs et utilisateurs internes.
- Interface utilisateur claire pour visualiser et gérer les ESL et templates.
- Affichage des notifications pour les actions réussies ou les erreurs.

---

## Communication externe

Ce module communique avec l’API ESL Hpharma : `https://blev29.kalanda.info` pour :

- Récupérer la **clé publique** pour le chiffrement des mots de passe.
- Demander un **token d’authentification sécurisé**.
- Envoyer les informations des produits (barcodes, prix, stock) pour affichage sur les étiquettes électroniques.
- Récupérer les **templates d’étiquettes ESL**.
- Lier/délier les ESL avec les produits.

⚠️ **Aucune donnée personnelle des clients n’est transmise.**  
Les seuls identifiants envoyés sont ceux des magasins (`uniqueId`, `agencyId`, `merchantId`) et les tokens d’accès sécurisés.

---

## Installation

1. Copier le dossier du module dans `addons/` de ton instance Odoo.
2. Mettre à jour la liste des modules dans Odoo.
3. Installer le module **Hpharma ESL System** via l’interface Odoo.

---

## Configuration

1. Créer un enregistrement ESL dans **ESL System**.
2. Saisir les identifiants de connexion (`login`, `password`) et le `uniqueId`.
3. Activer la planification automatique si souhaité.
4. Synchroniser les templates d’étiquettes via l’interface.
5. Lier ou délier les ESL aux produits depuis l’interface dédiée.

---

## Sécurité et droits d’accès

- **Administrateur Odoo** : accès complet (lecture, écriture, création, suppression).  
- **Utilisateurs internes** : accès complet pour gérer les ESL et les templates, visualiser les données et lier/délier les ESL.

---

## Journaux / Logs

- Les logs **ne contiennent pas de données sensibles** (tokens et mots de passe sont masqués).  
- Seuls les identifiants non sensibles et informations sur les produits sont loggés pour débogage.

---

## Dépendances

- Odoo ≥ 18  
- Python packages : `requests`, `cryptography`  

---

## Licence

Ce module est distribué sous la licence **OPL-1 (Odoo Proprietary License v1.0)**.  
Voir [OPL-1](https://www.odoo.com/documentation/16.0/fr/legal/licenses.html) pour les détails.

---

## Support

Pour toute question ou problème, contacter **B.L.E.V. Sàrl**.
