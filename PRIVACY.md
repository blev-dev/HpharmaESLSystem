# Politique de confidentialité - Module Hpharma ESL System

## 1. Collecte des données

Le module **Hpharma ESL System** ne collecte **aucune donnée personnelle des clients**.  
Les seules informations transmises à l’API externe sont :

- Identifiants du magasin : `uniqueId`, `agencyId`, `merchantId`  
- Identifiants de connexion ESL sécurisés : `token`, `zk_token`  
- Informations sur les produits : barcodes, prix, stock (aucune donnée client)

Ces données sont strictement nécessaires pour le fonctionnement du module.

---

## 2. Finalité des données

Les informations transmises sont utilisées uniquement pour :

- Authentifier le magasin auprès de l’API ESL  
- Envoyer les informations des produits pour affichage sur les étiquettes électroniques  
- Synchroniser les templates d’étiquettes ESL  
- Lier ou délier les ESL avec les produits

---

## 3. Conservation et sécurité

- Les tokens et identifiants sont stockés **chiffrés** dans la base Odoo.  
- Les logs ne contiennent **aucune donnée sensible** (tokens et mots de passe sont masqués).  
- Les informations sont conservées uniquement pour le bon fonctionnement du module et peuvent être supprimées à tout moment par l’administrateur.

---

## 4. Partage avec des tiers

- Les données sont uniquement envoyées à l’API officielle **Hpharma ESL** (`https://blev29.kalanda.info`).  
- **Aucune donnée personnelle des clients** n’est partagée avec des tiers.

---

## 5. Droits des utilisateurs

- L’administrateur Odoo peut accéder, modifier ou supprimer toutes les informations stockées par le module.  
- Les utilisateurs internes ont accès uniquement aux fonctionnalités nécessaires à la gestion des ESL et des templates.  

---

## 6. Consentement

- En utilisant ce module, l’administrateur consent à la transmission des données nécessaires au fonctionnement des ESL.  
- Aucune donnée personnelle des clients n’est utilisée sans consentement explicite.

---

## 7. Contact

Pour toute question concernant la confidentialité et le traitement des données, contactez :

**B.L.E.V. Sàrl**  
Email : [development@blev.lu]
