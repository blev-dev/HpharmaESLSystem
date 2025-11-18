# -*- coding: utf-8 -*-
{
    'name': "Module Hpharma ESL System",
    'summary': "Module electronic label",
    'description': """
    Module Hpharma ESL System
    -------------------------
    Ce module permet :
    - La connexion aux ESL Hpharma via API sécurisée.
    - L'envoi et la synchronisation des produits.
    - La récupération et gestion des templates d'étiquettes.
    - La liaison/déliaison (bind/unbind) des ESL avec les produits.
    - Gestion de tâches planifiées (cron) pour envoi automatique.
    - Notifications et suivi des erreurs.
    """,
    'author': "B.L.E.V. Sàrl",
    'license': 'OPL-1',
    'version': '19.0.1.0',
    'category': 'Supply Chain/Inventory',
    'depends': ['base','product','stock','sale_management'],

    # ✅ Données XML, CSV, etc.
    'data' : [
        "security/ir.model.access.csv",
        'data/esl_data.xml',
        'views/views.xml',
        'views/views_bind_unbind.xml',
        'views/views_esl_template.xml',
        'views/views_menu.xml',
        'data/ir_cron.xml',
    ],

    # ✅ Hooks
    #'post_init_hook': 'clear_esl_templates',
    #'uninstall_hook': 'clear_esl_templates',


    # ✅ Options du module
    'installable': True,
    'application': True,

    # ✅ Dépendances externes
    'external_dependencies': {
        'python': ['requests', 'cryptography'],
    },
}
