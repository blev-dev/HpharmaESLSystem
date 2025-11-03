
def clear_esl_templates(cr, registry):
    """Vide la table esl.template à chaque installation/mise à jour du module"""
    cr.execute("DELETE FROM esl_template")
