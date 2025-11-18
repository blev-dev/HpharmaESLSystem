from odoo import api, SUPERUSER_ID
import logging

_logger = logging.getLogger(__name__)

def clear_esl_templates(env):
    """Vide la table esl_template lors de la désinstallation du module."""
    cr = env.cr
    try:
        cr.execute("DELETE FROM esl_template")
        _logger.info("✅ [Hpharma ESL] Table esl_template vidée avec succès.")
    except Exception as e:
        cr.rollback()
        _logger.error(f"❌ [Hpharma ESL] Erreur lors du nettoyage des templates ESL : {e}")
