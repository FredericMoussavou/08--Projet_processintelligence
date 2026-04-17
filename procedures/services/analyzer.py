import networkx as nx
from collections import Counter
from procedures.models import Procedure, Step, StepDependency, AuditReport


def build_graph(procedure: Procedure) -> nx.DiGraph:
    """
    Construit un graphe orienté à partir des étapes d'une procédure.
    Chaque nœud = une étape (identifiée par son ID)
    Chaque arête = une dépendance entre deux étapes

    Si aucune StepDependency n'existe, on crée des arêtes
    séquentielles automatiquement (étape 1→2→3...).
    """
    G = nx.DiGraph()

    steps = Step.objects.filter(procedure=procedure).order_by('step_order')

    # Ajout des nœuds avec leurs attributs
    for step in steps:
        G.add_node(step.id, **{
            'title'           : step.title,
            'actor_role'      : step.actor_role,
            'action_verb'     : step.action_verb,
            'output_type'     : step.output_type,
            'automation_score': step.automation_score,
            'is_recurring'    : step.is_recurring,
            'has_condition'   : step.has_condition,
            'step_order'      : step.step_order,
        })

    # Ajout des arêtes depuis StepDependency
    dependencies = StepDependency.objects.filter(
        from_step__procedure=procedure
    )

    if dependencies.exists():
        for dep in dependencies:
            G.add_edge(dep.from_step.id, dep.to_step.id,
                      condition=dep.condition_label)
    else:
        # Pas de dépendances définies → on relie séquentiellement
        step_list = list(steps)
        for i in range(len(step_list) - 1):
            G.add_edge(step_list[i].id, step_list[i + 1].id, condition='')

    return G


def detect_infinite_loops(G: nx.DiGraph) -> list:
    """
    Détecte les cycles dans le graphe (boucles infinies potentielles).
    Utilise l'algorithme de détection de cycles de NetworkX.

    Retourne une liste de cycles, chaque cycle étant une liste d'IDs d'étapes.
    """
    anomalies = []

    try:
        cycles = list(nx.simple_cycles(G))
        for cycle in cycles:
            # Récupère les titres des étapes du cycle
            cycle_titles = []
            for node_id in cycle:
                node_data = G.nodes[node_id]
                cycle_titles.append(
                    f"Étape {node_data.get('step_order', '?')} "
                    f"({node_data.get('title', '')[:40]})"
                )

            anomalies.append({
                'type'       : 'infinite_loop',
                'severity'   : 'high',
                'description': f"Boucle détectée entre : {' → '.join(cycle_titles)}",
                'step_ids'   : cycle,
            })
    except nx.NetworkXError:
        pass

    return anomalies


def detect_congestion_points(procedure: Procedure, G: nx.DiGraph) -> list:
    """
    Détecte les acteurs surchargés — un acteur qui apparaît
    sur plus de 40% des étapes est un point de défaillance potentiel.
    """
    anomalies = []
    steps = Step.objects.filter(procedure=procedure)
    total_steps = steps.count()

    if total_steps == 0:
        return anomalies

    # Compte les occurrences de chaque acteur
    actor_counts = Counter(
        s.actor_role.strip().lower()
        for s in steps
        if s.actor_role.strip()
    )

    threshold = 0.4  # 40% des étapes

    for actor, count in actor_counts.items():
        ratio = count / total_steps
        if ratio >= threshold:
            anomalies.append({
                'type'       : 'congestion_point',
                'severity'   : 'medium',
                'description': (
                    f"L'acteur '{actor.title()}' intervient sur {count}/{total_steps} étapes "
                    f"({round(ratio * 100)}%) — risque de goulot d'étranglement."
                ),
                'actor'      : actor,
                'count'      : count,
                'ratio'      : round(ratio, 2),
            })

    return anomalies


def detect_orphan_tasks(procedure: Procedure, G: nx.DiGraph) -> list:
    """
    Détecte les tâches orphelines — étapes sans output utile.
    Une étape avec output_type='none' ne produit rien de tangible.
    """
    anomalies = []
    steps = Step.objects.filter(procedure=procedure, output_type=Step.OUTPUT_NONE)

    for step in steps:
        anomalies.append({
            'type'       : 'orphan_task',
            'severity'   : 'low',
            'description': (
                f"L'étape '{step.title[:60]}' ne produit aucun output identifiable "
                f"— vérifier sa valeur ajoutée."
            ),
            'step_id'    : step.id,
            'step_order' : step.step_order,
        })

    return anomalies


def calculate_optimization_score(procedure: Procedure, anomalies: list) -> float:
    """
    Calcule un score d'optimisation global entre 0.0 et 1.0.

    Logique de pénalités :
    - Boucle infinie        : -0.25 par boucle
    - Point de congestion   : -0.15 par acteur surchargé
    - Tâche orpheline       : -0.05 par tâche

    Un score de 1.0 = procédure parfaite (aucune anomalie).
    """
    score = 1.0

    for anomaly in anomalies:
        if anomaly['type'] == 'infinite_loop':
            score -= 0.25
        elif anomaly['type'] == 'congestion_point':
            score -= 0.15
        elif anomaly['type'] == 'orphan_task':
            score -= 0.05

    return round(max(0.0, score), 2)


def calculate_global_automation_score(procedure: Procedure) -> float:
    """
    Calcule le score d'automatisation moyen de toutes les étapes.
    """
    steps = Step.objects.filter(procedure=procedure)
    if not steps.exists():
        return 0.0

    total = sum(s.automation_score for s in steps)
    return round(total / steps.count(), 2)


def generate_recommendations(anomalies: list) -> list:
    """
    Génère des recommandations textuelles basées sur les anomalies détectées.
    En Phase 4, ces recommandations seront enrichies par un LLM.
    """
    recommendations = []

    for anomaly in anomalies:
        if anomaly['type'] == 'infinite_loop':
            recommendations.append({
                'priority'  : 'high',
                'action'    : 'Ajouter une condition de sortie explicite '
                              'pour éviter la boucle détectée.',
                'related_to': anomaly['description'],
            })
        elif anomaly['type'] == 'congestion_point':
            recommendations.append({
                'priority'  : 'medium',
                'action'    : (
                    f"Déléguer certaines tâches de '{anomaly['actor'].title()}' "
                    f"à d'autres acteurs pour réduire la charge."
                ),
                'related_to': anomaly['description'],
            })
        elif anomaly['type'] == 'orphan_task':
            recommendations.append({
                'priority'  : 'low',
                'action'    : 'Définir un output clair pour cette étape '
                              'ou envisager sa suppression.',
                'related_to': anomaly['description'],
            })

    return recommendations


def analyze_procedure(procedure_id: int) -> dict:
    """
    Fonction principale du moteur d'analyse.
    Orchestre toutes les analyses et sauvegarde le rapport en base.

    Retourne un dictionnaire complet avec :
    - Le graphe (nombre de nœuds/arêtes)
    - Toutes les anomalies détectées
    - Les scores (optimisation + automatisation)
    - Les recommandations
    """
    try:
        procedure = Procedure.objects.get(id=procedure_id)
    except Procedure.DoesNotExist:
        return {'success': False, 'error': 'Procédure introuvable'}

    # Construction du graphe
    G = build_graph(procedure)

    # Détection des anomalies
    anomalies = []
    anomalies += detect_infinite_loops(G)
    anomalies += detect_congestion_points(procedure, G)
    anomalies += detect_orphan_tasks(procedure, G)

    # Calcul des scores
    score_optim = calculate_optimization_score(procedure, anomalies)
    score_auto  = calculate_global_automation_score(procedure)

    # Génération des recommandations
    recommendations = generate_recommendations(anomalies)

    # Sauvegarde du rapport en base
    report = AuditReport.objects.create(
        procedure       = procedure,
        score_optim     = score_optim,
        score_auto      = score_auto,
        anomalies       = anomalies,
        recommendations = recommendations,
    )

    return {
        'success'        : True,
        'procedure_id'   : procedure.id,
        'procedure_title': procedure.title,
        'graph'          : {
            'nodes': G.number_of_nodes(),
            'edges': G.number_of_edges(),
        },
        'scores'         : {
            'optimization' : score_optim,
            'automation'   : score_auto,
        },
        'anomalies'      : anomalies,
        'recommendations': recommendations,
        'report_id'      : report.id,
    }