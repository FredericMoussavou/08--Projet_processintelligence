"""
Définition des plans d'abonnement de ProcessIntelligence.

Source de vérité unique pour :
    - La liste des plans disponibles
    - Les limites techniques de chaque plan (procédures, utilisateurs, analyses/mois, etc.)
    - Les features activées par plan (LLM, export BPMN, thèmes, etc.)
    - Le mapping plan → modèle LLM utilisé

IMPORTANT : ce fichier est importé à la fois par le backend (vérifications
de limites) et par une API frontend (pour afficher les paywalls, badges, etc.).
Ne pas y mettre de logique Django complexe — juste des données structurées.
"""

# ---------------------------------------------------------------------------
# Identifiants de plans
# ---------------------------------------------------------------------------

PLAN_FREE = "free"
PLAN_PRO = "pro"
PLAN_BUSINESS = "business"

# Ordre hiérarchique : un plan "supérieur" inclut tout ce que les plans "inférieurs" proposent
PLAN_HIERARCHY = [PLAN_FREE, PLAN_PRO, PLAN_BUSINESS]


# ---------------------------------------------------------------------------
# Définition complète de chaque plan
# ---------------------------------------------------------------------------
#
# Convention :
#   - limit_* : nombre maximum (None = illimité)
#   - feature_* : booléen d'activation de feature
#   - llm_model : None si pas d'accès LLM, sinon identifiant du modèle à utiliser

PLANS = {
    PLAN_FREE: {
        "id":           PLAN_FREE,
        "name":         "Free",
        "description":  "Idéal pour découvrir ProcessIntelligence",
        "is_paid":      False,
        "sort_order":   1,

        # --- Limites de stockage ---
        "limit_procedures":          5,
        "limit_users":               2,
        "limit_services":            1,
        "limit_analyses_per_month":  10,

        # --- Features techniques ---
        "llm_model":                 None,                  # spaCy only
        "feature_export_pdf_themed": False,                 # PDF basique seulement
        "feature_export_bpmn":       False,
        "feature_export_manual":     False,
        "feature_versioning":        False,
        "feature_change_workflow":   "basic",               # basic / full
        "feature_rules_sectors":     ["generic"],           # seulement règles génériques
        "feature_custom_theme":      False,
        "feature_sso":               False,
        "feature_priority_support":  False,
    },

    PLAN_PRO: {
        "id":           PLAN_PRO,
        "name":         "Pro",
        "description":  "Pour les équipes qui veulent automatiser leurs procédures",
        "is_paid":      True,
        "sort_order":   2,

        "limit_procedures":          100,
        "limit_users":               15,
        "limit_services":            None,                   # illimité
        "limit_analyses_per_month":  500,

        "llm_model":                 "claude-haiku-4-5-20251001",
        "feature_export_pdf_themed": True,
        "feature_export_bpmn":       True,
        "feature_export_manual":     True,
        "feature_versioning":        True,
        "feature_change_workflow":   "full",
        "feature_rules_sectors":     ["generic", "finance", "hr", "health", "food", "insurance"],
        "feature_custom_theme":      False,
        "feature_sso":               False,
        "feature_priority_support":  False,
    },

    PLAN_BUSINESS: {
        "id":           PLAN_BUSINESS,
        "name":         "Business",
        "description":  "Pour les organisations à forte volumétrie",
        "is_paid":      True,
        "sort_order":   3,

        "limit_procedures":          None,
        "limit_users":               None,
        "limit_services":            None,
        "limit_analyses_per_month":  None,

        "llm_model":                 "claude-sonnet-4-6",   # modèle plus précis
        "feature_export_pdf_themed": True,
        "feature_export_bpmn":       True,
        "feature_export_manual":     True,
        "feature_versioning":        True,
        "feature_change_workflow":   "full",
        "feature_rules_sectors":     ["generic", "finance", "hr", "health", "food", "insurance"],
        "feature_custom_theme":      True,
        "feature_sso":               True,
        "feature_priority_support":  True,
    },
}


# ---------------------------------------------------------------------------
# Choices Django pour le champ models.CharField(choices=...)
# ---------------------------------------------------------------------------

PLAN_CHOICES = [
    (PLAN_FREE,     "Free"),
    (PLAN_PRO,      "Pro"),
    (PLAN_BUSINESS, "Business"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_plan(plan_id: str) -> dict:
    """
    Retourne la définition complète d'un plan.
    Fallback sur Free si l'ID est inconnu (par sécurité — on ne donne jamais
    accès à des features supérieures en cas de donnée corrompue).
    """
    return PLANS.get(plan_id, PLANS[PLAN_FREE])


def is_plan_at_least(current_plan: str, required_plan: str) -> bool:
    """
    Vérifie qu'un plan atteint au moins un niveau requis.

    Exemple :
        is_plan_at_least('pro', 'free')      → True
        is_plan_at_least('pro', 'pro')       → True
        is_plan_at_least('pro', 'business')  → False
        is_plan_at_least('free', 'pro')      → False
    """
    try:
        return PLAN_HIERARCHY.index(current_plan) >= PLAN_HIERARCHY.index(required_plan)
    except ValueError:
        return False


def get_public_plans() -> list[dict]:
    """
    Retourne la liste des plans à exposer via l'API publique (pour le frontend).
    Exclut les champs internes et trie par ordre.
    """
    result = []
    for plan in sorted(PLANS.values(), key=lambda p: p["sort_order"]):
        result.append({
            "id":           plan["id"],
            "name":         plan["name"],
            "description":  plan["description"],
            "is_paid":      plan["is_paid"],
            "limits": {
                "procedures":         plan["limit_procedures"],
                "users":              plan["limit_users"],
                "services":           plan["limit_services"],
                "analyses_per_month": plan["limit_analyses_per_month"],
            },
            "features": {
                "llm_enabled":        plan["llm_model"] is not None,
                "export_pdf_themed":  plan["feature_export_pdf_themed"],
                "export_bpmn":        plan["feature_export_bpmn"],
                "export_manual":      plan["feature_export_manual"],
                "versioning":         plan["feature_versioning"],
                "custom_theme":       plan["feature_custom_theme"],
                "sso":                plan["feature_sso"],
                "priority_support":   plan["feature_priority_support"],
                "rules_sectors":      plan["feature_rules_sectors"],
            },
        })
    return result
