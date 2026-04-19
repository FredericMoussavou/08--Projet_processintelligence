"""
Script de test du parser. Lance :
    python -m procedures.services.test_parser
"""

from procedures.services.parser import parse_procedure_text


TEST_CASES = [
    {
        "name": "RH — Recrutement basique",
        "text": (
            "Le RH publie l'offre sur LinkedIn. "
            "Le manager analyse les CV reçus. "
            "Si un candidat est retenu, le RH organise un entretien."
        ),
    },
    {
        "name": "Coordination — 'puis'",
        "text": (
            "Le comptable saisit la facture dans SAP puis la transmet au directeur financier "
            "qui valide le paiement."
        ),
    },
    {
        "name": "Voix passive",
        "text": (
            "Le dossier est validé par le manager. "
            "Les données sont ensuite saisies dans Excel par l'assistante."
        ),
    },
    {
        "name": "Liste numérotée",
        "text": (
            "1. Recevoir la demande du client par email.\n"
            "2. Vérifier l'éligibilité dans le CRM.\n"
            "3. Créer le dossier dans SharePoint.\n"
            "4. Notifier le commercial."
        ),
    },
    {
        "name": "Anaphores (il / on)",
        "text": (
            "Le manager reçoit la demande. "
            "Il vérifie ensuite la disponibilité des ressources. "
            "On archive ensuite le dossier dans SharePoint."
        ),
    },
    {
        "name": "Récurrences",
        "text": (
            "Chaque mois, le comptable extrait les factures de SAP. "
            "À chaque nouvelle demande client, le commercial crée une fiche dans Salesforce. "
            "Le rapport annuel est généré en fin d'année."
        ),
    },
    {
        "name": "Nominalisation",
        "text": (
            "La validation du dossier par le manager est obligatoire. "
            "L'archivage des documents doit se faire dans SharePoint."
        ),
    },
    {
        "name": "Conditions",
        "text": (
            "Si le montant dépasse 500 euros, le directeur financier valide la dépense. "
            "En cas de refus, le demandeur reçoit une notification par email. "
            "Lorsque le paiement est effectué, le comptable archive la pièce."
        ),
    },
    {
        "name": "Outil via préposition",
        "text": (
            "Le technicien consigne l'intervention via GLPI. "
            "Le résultat est saisi sur la plateforme interne."
        ),
    },
]


def print_step(s):
    flag = " [LISTE GÉNÉRIQUE]" if s.is_generic_instruction else ""
    print(f"  #{s.order} — {s.title}{flag}")
    print(f"      verbe    : {s.action_verb!r:25} (conf: {s.confidence.get('action_verb', 0):.2f})")
    print(f"      acteur   : {s.actor_role!r:25} (conf: {s.confidence.get('actor_role', 0):.2f})")
    print(f"      outil    : {s.tool_used!r:25} (conf: {s.confidence.get('tool_used', 0):.2f})")
    print(f"      objet    : {s.object!r}")
    if s.has_condition:
        print(f"      condition: '{s.trigger_condition}' (conf: {s.confidence.get('condition', 0):.2f})")
    if s.is_recurring:
        print(f"      récurrence: {s.frequency} (conf: {s.confidence.get('recurrence', 0):.2f})")
    print(f"      output   : {s.output_type}  |  auto_score: {s.automation_score}")
    print()


def main():
    for case in TEST_CASES:
        print("=" * 80)
        print(f"CAS : {case['name']}")
        print(f"TEXTE : {case['text']}")
        print("-" * 80)
        steps = parse_procedure_text(case["text"])
        if not steps:
            print("  (aucune étape extraite)")
            continue
        for s in steps:
            print_step(s)


if __name__ == "__main__":
    main()
