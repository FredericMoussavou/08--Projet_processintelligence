# ProcessIntelligence

SaaS d'audit et de modélisation des procédures d'entreprise.

## Concept
Uploadez vos procédures existantes ou décrivez ce que vous souhaitez
faire — l'outil identifie les dysfonctionnements, évalue le potentiel
d'automatisation et génère un manuel de procédures prêt à l'emploi.

## Stack technique
- Backend : Python 3.13 / Django 5
- Base de données : PostgreSQL
- NLP : spaCy (fr_core_news_md)
- Graphes : NetworkX
- Auth : JWT (djangorestframework-simplejwt)
- Export : ReportLab (PDF), lxml (BPMN 2.0)

## API Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/auth/register/ | Inscription |
| POST | /api/auth/login/ | Connexion |
| POST | /api/procedures/ingest/ | Ingestion texte/PDF/DOCX/CSV |
| POST | /api/procedures/:id/analyze/ | Analyse + scoring |
| POST | /api/procedures/:id/compliance/ | Vérification conformité |
| GET  | /api/procedures/:id/export/pdf/ | Rapport audit PDF |
| GET  | /api/procedures/:id/export/bpmn/ | Export BPMN 2.0 |
| GET  | /api/procedures/manual/:org_id/ | Manuel de procédures |
| POST | /api/procedures/change-requests/ | Workflow de validation |

## Statut
��� Backend complet — Frontend en cours de développement

## Déploiement
Railway (à venir)
