from odoo import api, SUPERUSER_ID
import logging

_logger = logging.getLogger(__name__)

def clear_esl_templates(cr, registry):
    """Vide la table esl.template à chaque installation/mise à jour du module."""
    try:
        cr.execute("DELETE FROM esl_template")
        _logger.info("✅ [Hpharma ESL] Table esl_template vidée avec succès.")
    except Exception as e:
        cr.rollback()
        _logger.error(f"❌ [Hpharma ESL] Erreur lors du nettoyage des templates ESL : {e}")
