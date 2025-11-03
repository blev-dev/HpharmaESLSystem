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
    'version': '18.0.1.2',
    'category': 'Warehouse/Inventory, Sales/Point of Sale',
    'depends': ['base','product','stock','sale_management'],
    'data' : [
        "security/ir.model.access.csv",
        'data/esl_data.xml',
        'views/views.xml',
        'views/views_bind_unbind.xml',
        'views/views_esl_template.xml',
        'views/views_menu.xml',
        'data/ir_cron.xml',
    ],
    "post_init_hook": "clear_esl_templates",
    "uninstall_hook": "clear_esl_templates",
    'installable': True,
    'application': True,
    'external_dependencies': {
        'python': ['requests', 'cryptography'],
    },
}
