import spacy
from dataclasses import dataclass, field

nlp = spacy.load('fr_core_news_md')

# Verbes qui indiquent une forte automatisabilité
HIGH_AUTOMATION_VERBS = {
    'saisir', 'copier', 'coller', 'extraire', 'importer', 'exporter',
    'envoyer', 'transférer', 'télécharger', 'uploader', 'archiver',
    'classer', 'trier', 'filtrer', 'calculer', 'générer', 'créer',
    'mettre à jour', 'modifier', 'supprimer', 'notifier', 'alerter',
}

# Verbes qui indiquent une décision humaine (faible automatisabilité)
LOW_AUTOMATION_VERBS = {
    'valider', 'approuver', 'décider', 'juger', 'évaluer', 'négocier',
    'analyser', 'interpréter', 'conseiller', 'arbitrer', 'superviser',
}

# Mots qui indiquent une condition (Si/Alors)
CONDITION_WORDS = {
    'si', 'sinon', 'selon', 'dans le cas', 'en cas', 'lorsque',
    'quand', 'dès que', 'à condition', 'sauf si', 'sauf',
}

# Mots qui indiquent une récurrence
RECURRENCE_WORDS = {
    'chaque', 'tous les', 'toutes les', 'quotidien', 'hebdomadaire',
    'mensuel', 'annuel', 'régulièrement', 'périodiquement',
    'chaque jour', 'chaque semaine', 'chaque mois',
}

# Outils courants détectés automatiquement
KNOWN_TOOLS = {
    'excel', 'word', 'powerpoint', 'outlook', 'teams', 'slack',
    'sap', 'sage', 'odoo', 'salesforce', 'hubspot', 'jira',
    'gmail', 'google drive', 'sharepoint', 'notion', 'trello',
    'email', 'mail', 'téléphone', 'pdf', 'erp', 'crm',
}


@dataclass
class ParsedStep:
    """
    Représente une étape extraite du texte.
    Cette structure sera ensuite utilisée pour créer les objets Step en base.
    """
    order: int
    title: str
    action_verb: str = ''
    actor_role: str = ''
    tool_used: str = ''
    has_condition: bool = False
    is_recurring: bool = False
    output_type: str = 'none'
    automation_score: float = 0.0
    raw_sentence: str = ''


def _extract_verb(sent) -> str:
    """Extrait le verbe principal d'une phrase spaCy."""
    for token in sent:
        if token.pos_ == 'VERB' and token.dep_ in ('ROOT', 'acl', 'relcl'):
            return token.lemma_.lower()
    # Fallback : premier verbe trouvé
    for token in sent:
        if token.pos_ == 'VERB':
            return token.lemma_.lower()
    return ''


def _extract_actor(sent) -> str:
    """
    Extrait le sujet/acteur d'une phrase.
    Cherche le sujet du verbe principal (nsubj) ou une entité NER de type PER/ORG.
    """
    # Cherche le sujet grammatical
    for token in sent:
        if token.dep_ in ('nsubj', 'nsubj:pass'):
            # Récupère le groupe nominal complet
            subtree = [t.text for t in token.subtree
                      if t.dep_ not in ('punct', 'cc')]
            return ' '.join(subtree).strip()

    # Fallback : première entité PER ou ORG de la phrase
    for ent in sent.ents:
        if ent.label_ in ('PER', 'ORG'):
            return ent.text

    return ''


def _extract_tool(sent) -> str:
    """Détecte si un outil connu est mentionné dans la phrase."""
    text_lower = sent.text.lower()
    for tool in KNOWN_TOOLS:
        if tool in text_lower:
            return tool.capitalize()
    return ''


def _detect_condition(sent) -> bool:
    """Détecte la présence d'une condition Si/Alors."""
    text_lower = sent.text.lower()
    return any(word in text_lower for word in CONDITION_WORDS)


def _detect_recurrence(sent) -> bool:
    """Détecte la présence d'une récurrence."""
    text_lower = sent.text.lower()
    return any(word in text_lower for word in RECURRENCE_WORDS)


def _calculate_automation_score(verb: str, has_condition: bool,
                                 is_recurring: bool, tool: str) -> float:
    """
    Calcule un score d'automatisation entre 0.0 et 1.0.

    Logique :
    - Verbe à haute automatisabilité  → +0.4
    - Verbe à faible automatisabilité → -0.3
    - Tâche récurrente                → +0.3
    - Outil détecté                   → +0.2
    - Condition Si/Alors              → -0.1 (complexifie l'automatisation)
    """
    score = 0.3  # Score de base

    if verb in HIGH_AUTOMATION_VERBS:
        score += 0.4
    elif verb in LOW_AUTOMATION_VERBS:
        score -= 0.3

    if is_recurring:
        score += 0.3

    if tool:
        score += 0.2

    if has_condition:
        score -= 0.1

    # On s'assure que le score reste entre 0.0 et 1.0
    return round(max(0.0, min(1.0, score)), 2)


def _determine_output_type(sent) -> str:
    """
    Détermine le type d'output produit par l'étape.
    Basé sur des mots clés dans la phrase.
    """
    text_lower = sent.text.lower()

    document_words = ['document', 'rapport', 'contrat', 'fichier', 'formulaire',
                      'fiche', 'pdf', 'courrier', 'lettre', 'attestation']
    data_words = ['données', 'information', 'saisie', 'enregistre', 'base',
                  'tableau', 'liste', 'calcul', 'résultat']
    decision_words = ['valide', 'approuve', 'décide', 'refuse', 'accepte',
                      'rejette', 'autorise', 'signe']

    if any(w in text_lower for w in decision_words):
        return 'decision'
    if any(w in text_lower for w in document_words):
        return 'document'
    if any(w in text_lower for w in data_words):
        return 'data'
    return 'none'


def parse_procedure_text(text: str) -> list[ParsedStep]:
    """
    Fonction principale du parser.
    Prend un texte libre décrivant une procédure et retourne
    une liste de ParsedStep ordonnés.

    Exemple d'input :
        "Le RH publie l'offre sur LinkedIn. Le manager analyse les CVs.
         Si un candidat est retenu, le RH organise un entretien."

    Exemple d'output :
        [ParsedStep(order=1, title="Publier l'offre", actor_role="RH", ...),
         ParsedStep(order=2, title="Analyser les CVs", actor_role="Manager", ...),
         ...]
    """
    doc = nlp(text)
    steps = []
    order = 1

    for sent in doc.sents:
        # Ignore les phrases trop courtes (moins de 4 tokens)
        if len(sent) < 4:
            continue

        # Extraction des informations
        verb        = _extract_verb(sent)
        actor       = _extract_actor(sent)
        tool        = _extract_tool(sent)
        has_cond    = _detect_condition(sent)
        is_recur    = _detect_recurrence(sent)
        output      = _determine_output_type(sent)
        auto_score  = _calculate_automation_score(verb, has_cond, is_recur, tool)

        # Construction du titre de l'étape
        # On prend la phrase nettoyée, limitée à 100 caractères
        title = sent.text.strip()
        if len(title) > 100:
            title = title[:97] + '...'

        step = ParsedStep(
            order          = order,
            title          = title,
            action_verb    = verb,
            actor_role     = actor,
            tool_used      = tool,
            has_condition  = has_cond,
            is_recurring   = is_recur,
            output_type    = output,
            automation_score = auto_score,
            raw_sentence   = sent.text.strip(),
        )
        steps.append(step)
        order += 1

    return steps