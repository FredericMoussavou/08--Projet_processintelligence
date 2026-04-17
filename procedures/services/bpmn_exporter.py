from lxml import etree
from procedures.models import Procedure


# Namespaces BPMN 2.0 standards
NAMESPACES = {
    'bpmn'  : 'http://www.omg.org/spec/BPMN/20100524/MODEL',
    'bpmndi': 'http://www.omg.org/spec/BPMN/20100524/DI',
    'dc'    : 'http://www.omg.org/spec/DD/20100524/DC',
    'di'    : 'http://www.omg.org/spec/DD/20100524/DI',
    'xsi'   : 'http://www.w3.org/2001/XMLSchema-instance',
}

# Dimensions des éléments visuels
TASK_W      = 160
TASK_H      = 60
TASK_GAP    = 40
START_R     = 18
END_R       = 18
MARGIN_X    = 100
MARGIN_Y    = 200


def generate_bpmn(procedure_id: int) -> bytes:
    """
    Génère un fichier BPMN 2.0 complet pour une procédure.
    Inclut les éléments sémantiques ET les informations de rendu visuel (DI).
    Retourne les bytes XML du fichier .bpmn
    """
    try:
        procedure = Procedure.objects.get(id=procedure_id)
    except Procedure.DoesNotExist:
        raise ValueError(f"Procédure introuvable : {procedure_id}")

    steps = list(procedure.steps.all().order_by('step_order'))

    # ── Racine XML ──────────────────────────────────
    root = etree.Element(
        f"{{{NAMESPACES['bpmn']}}}definitions",
        nsmap=NAMESPACES,
        attrib={
            'id'              : f"definitions_{procedure.id}",
            'targetNamespace' : 'http://processintelligence.io/bpmn',
            'exporter'        : 'ProcessIntelligence',
            'exporterVersion' : '1.0',
        }
    )

    # ── Process ─────────────────────────────────────
    process_id = f"process_{procedure.id}"
    process = etree.SubElement(
        root,
        f"{{{NAMESPACES['bpmn']}}}process",
        attrib={
            'id'         : process_id,
            'name'       : procedure.title,
            'isExecutable': 'false',
        }
    )

    # ── Start Event ─────────────────────────────────
    start_id = f"start_{procedure.id}"
    etree.SubElement(
        process,
        f"{{{NAMESPACES['bpmn']}}}startEvent",
        attrib={'id': start_id, 'name': 'Début'}
    )

    # ── Tasks (étapes) ──────────────────────────────
    task_ids = []
    for step in steps:
        task_id = f"task_{step.id}"
        task_ids.append(task_id)

        # Type de tâche selon le trigger
        task_tag = f"{{{NAMESPACES['bpmn']}}}task"
        if step.trigger_type == 'timer':
            task_tag = f"{{{NAMESPACES['bpmn']}}}intermediateCatchEvent"

        task = etree.SubElement(
            process,
            task_tag,
            attrib={
                'id'  : task_id,
                'name': f"{step.actor_role} : {step.action_verb or step.title[:40]}",
            }
        )

        # Annotations pour les métadonnées
        if step.tool_used:
            etree.SubElement(
                task,
                f"{{{NAMESPACES['bpmn']}}}documentation"
            ).text = f"Outil : {step.tool_used} | Score auto : {int(step.automation_score * 100)}%"

    # ── End Event ────────────────────────────────────
    end_id = f"end_{procedure.id}"
    etree.SubElement(
        process,
        f"{{{NAMESPACES['bpmn']}}}endEvent",
        attrib={'id': end_id, 'name': 'Fin'}
    )

    # ── Sequence Flows ───────────────────────────────
    # Start → Première tâche
    if task_ids:
        etree.SubElement(
            process,
            f"{{{NAMESPACES['bpmn']}}}sequenceFlow",
            attrib={
                'id'       : f"flow_start_{task_ids[0]}",
                'sourceRef': start_id,
                'targetRef': task_ids[0],
            }
        )

    # Tâche → Tâche suivante
    for i in range(len(task_ids) - 1):
        step     = steps[i]
        flow_id  = f"flow_{task_ids[i]}_{task_ids[i+1]}"

        flow = etree.SubElement(
            process,
            f"{{{NAMESPACES['bpmn']}}}sequenceFlow",
            attrib={
                'id'       : flow_id,
                'sourceRef': task_ids[i],
                'targetRef': task_ids[i + 1],
            }
        )

        # Si l'étape a une condition, on l'indique
        if step.has_condition:
            etree.SubElement(
                flow,
                f"{{{NAMESPACES['bpmn']}}}conditionExpression"
            ).text = "condition"

    # Dernière tâche → End
    if task_ids:
        etree.SubElement(
            process,
            f"{{{NAMESPACES['bpmn']}}}sequenceFlow",
            attrib={
                'id'       : f"flow_{task_ids[-1]}_end",
                'sourceRef': task_ids[-1],
                'targetRef': end_id,
            }
        )

    # ── Diagram (informations visuelles) ─────────────
    diagram = etree.SubElement(
        root,
        f"{{{NAMESPACES['bpmndi']}}}BPMNDiagram",
        attrib={'id': f"diagram_{procedure.id}"}
    )
    plane = etree.SubElement(
        diagram,
        f"{{{NAMESPACES['bpmndi']}}}BPMNPlane",
        attrib={
            'id'           : f"plane_{procedure.id}",
            'bpmnElement'  : process_id,
        }
    )

    # Position du Start Event
    x = MARGIN_X
    _add_shape(plane, start_id,
               x, MARGIN_Y - START_R,
               START_R * 2, START_R * 2)
    x += START_R * 2 + TASK_GAP

    # Position des tâches
    task_positions = {}
    for i, (step, task_id) in enumerate(zip(steps, task_ids)):
        _add_shape(plane, task_id, x, MARGIN_Y - TASK_H // 2, TASK_W, TASK_H)
        task_positions[task_id] = (x, MARGIN_Y)
        x += TASK_W + TASK_GAP

    # Position du End Event
    _add_shape(plane, end_id,
               x, MARGIN_Y - END_R,
               END_R * 2, END_R * 2)

    # Edges (flèches visuelles)
    # Start → première tâche
    if task_ids:
        _add_edge(plane,
                  f"flow_start_{task_ids[0]}",
                  MARGIN_X + START_R * 2, MARGIN_Y,
                  task_positions[task_ids[0]][0], MARGIN_Y)

    for i in range(len(task_ids) - 1):
        src = task_positions[task_ids[i]]
        tgt = task_positions[task_ids[i + 1]]
        _add_edge(plane,
                  f"flow_{task_ids[i]}_{task_ids[i+1]}",
                  src[0] + TASK_W, src[1],
                  tgt[0], tgt[1])

    # Dernière tâche → End
    if task_ids:
        last_pos = task_positions[task_ids[-1]]
        _add_edge(plane,
                  f"flow_{task_ids[-1]}_end",
                  last_pos[0] + TASK_W, last_pos[1],
                  x, MARGIN_Y)

    return etree.tostring(root, pretty_print=True,
                          xml_declaration=True, encoding='UTF-8')


def _add_shape(plane, element_id: str, x: int, y: int, w: int, h: int):
    """Ajoute un élément visuel (nœud) au diagramme BPMN."""
    shape = etree.SubElement(
        plane,
        f"{{{NAMESPACES['bpmndi']}}}BPMNShape",
        attrib={
            'id'         : f"shape_{element_id}",
            'bpmnElement': element_id,
        }
    )
    etree.SubElement(
        shape,
        f"{{{NAMESPACES['dc']}}}Bounds",
        attrib={
            'x': str(x), 'y': str(y),
            'width': str(w), 'height': str(h),
        }
    )


def _add_edge(plane, flow_id: str, x1: int, y1: int, x2: int, y2: int):
    """Ajoute une flèche visuelle au diagramme BPMN."""
    edge = etree.SubElement(
        plane,
        f"{{{NAMESPACES['bpmndi']}}}BPMNEdge",
        attrib={
            'id'         : f"edge_{flow_id}",
            'bpmnElement': flow_id,
        }
    )
    etree.SubElement(
        edge,
        f"{{{NAMESPACES['di']}}}waypoint",
        attrib={'x': str(x1), 'y': str(y1)}
    )
    etree.SubElement(
        edge,
        f"{{{NAMESPACES['di']}}}waypoint",
        attrib={'x': str(x2), 'y': str(y2)}
    )