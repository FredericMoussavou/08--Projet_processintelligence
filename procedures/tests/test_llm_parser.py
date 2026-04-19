"""
Tests unitaires de procedures/services/llm_parser.py.

Ces tests utilisent des mocks pour l'API Anthropic : AUCUN vrai appel n'est fait.
Tu peux les lancer sans clé API valide.

Lance avec :
    python manage.py test procedures.tests.test_llm_parser -v 2
"""

import json
from unittest.mock import patch, MagicMock
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from organizations.models import Organization


# Exemple de réponse valide simulée de Claude
VALID_LLM_RESPONSE = {
    "steps": [
        {
            "order": 1,
            "title": "Publier l'offre",
            "action_verb": "publier",
            "actor_role": "RH",
            "tool_used": "LinkedIn",
            "object": "offre",
            "has_condition": False,
            "trigger_condition": "",
            "is_recurring": False,
            "frequency": "",
            "output_type": "none",
            "automation_score": 0.7,
            "raw_sentence": "Le RH publie l'offre sur LinkedIn.",
        },
        {
            "order": 2,
            "title": "Analyser les CV",
            "action_verb": "analyser",
            "actor_role": "Manager",
            "tool_used": "",
            "object": "cv",
            "has_condition": False,
            "trigger_condition": "",
            "is_recurring": False,
            "frequency": "",
            "output_type": "none",
            "automation_score": 0.2,
            "raw_sentence": "Le manager analyse les CV reçus.",
        },
    ],
}


def make_mock_message(json_content: dict, input_tokens: int = 150, output_tokens: int = 200):
    """
    Construit un objet Message simulé, tel que retourné par anthropic.messages.create().
    Reproduit la structure minimale attendue par notre code.
    """
    block = MagicMock()
    block.text = json.dumps(json_content)

    message = MagicMock()
    message.content = [block]
    message.usage.input_tokens = input_tokens
    message.usage.output_tokens = output_tokens
    return message


@override_settings(
    ANTHROPIC_API_KEY="test-fake-key-for-tests",
    LLM_PARSER_MODEL="claude-haiku-4-5-20251001",
    # Utilise le cache DB par défaut, pas besoin d'override ici
)
class LLMParserAPICallTests(TestCase):
    """Appel API avec mock — vérifie la structure et la conversion en ParsedStep."""

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    @patch("anthropic.Anthropic")
    def test_successful_call_returns_parsed_steps(self, mock_anthropic_class):
        """Un appel API réussi retourne une liste de ParsedStep."""
        from procedures.services.llm_parser import parse_procedure_text_llm

        # Mock du client et de sa méthode messages.create
        mock_client = MagicMock()
        mock_client.messages.create.return_value = make_mock_message(VALID_LLM_RESPONSE)
        mock_anthropic_class.return_value = mock_client

        steps = parse_procedure_text_llm("Le RH publie l'offre.")

        self.assertEqual(len(steps), 2)
        self.assertEqual(steps[0].action_verb, "publier")
        self.assertEqual(steps[0].actor_role, "RH")
        self.assertEqual(steps[0].tool_used, "LinkedIn")
        self.assertEqual(steps[1].action_verb, "analyser")
        self.assertEqual(steps[1].actor_role, "Manager")

    @patch("anthropic.Anthropic")
    def test_call_logs_llmcalllog_entry(self, mock_anthropic_class):
        """Un appel doit créer un record LLMCallLog avec les bons tokens."""
        from procedures.services.llm_parser import parse_procedure_text_llm
        from procedures.models import LLMCallLog

        mock_client = MagicMock()
        mock_client.messages.create.return_value = make_mock_message(
            VALID_LLM_RESPONSE, input_tokens=123, output_tokens=456
        )
        mock_anthropic_class.return_value = mock_client

        self.assertEqual(LLMCallLog.objects.count(), 0)

        parse_procedure_text_llm("Un texte.")

        self.assertEqual(LLMCallLog.objects.count(), 1)
        log = LLMCallLog.objects.first()
        self.assertEqual(log.input_tokens, 123)
        self.assertEqual(log.output_tokens, 456)
        self.assertFalse(log.cache_hit)
        self.assertFalse(log.fallback_used)
        self.assertEqual(log.model, "claude-haiku-4-5-20251001")

    @patch("anthropic.Anthropic")
    def test_call_with_markdown_fences_in_response(self, mock_anthropic_class):
        """Le parser doit nettoyer les ```json ... ``` si Claude en ajoute."""
        from procedures.services.llm_parser import parse_procedure_text_llm

        # On simule une réponse avec des fences markdown autour du JSON
        wrapped_json = "```json\n" + json.dumps(VALID_LLM_RESPONSE) + "\n```"
        block = MagicMock()
        block.text = wrapped_json
        message = MagicMock()
        message.content = [block]
        message.usage.input_tokens = 100
        message.usage.output_tokens = 100

        mock_client = MagicMock()
        mock_client.messages.create.return_value = message
        mock_anthropic_class.return_value = mock_client

        steps = parse_procedure_text_llm("Un texte.")

        # Si le nettoyage n'avait pas marché, on aurait 0 étape (JSON invalide)
        self.assertEqual(len(steps), 2)


@override_settings(
    ANTHROPIC_API_KEY="test-fake-key-for-tests",
    LLM_PARSER_MODEL="claude-haiku-4-5-20251001",
)
class LLMParserCacheTests(TestCase):
    """Vérifie le comportement du cache."""

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    @patch("anthropic.Anthropic")
    def test_second_call_hits_cache(self, mock_anthropic_class):
        """Deux appels identiques → un seul appel API, le second vient du cache."""
        from procedures.services.llm_parser import parse_procedure_text_llm

        mock_client = MagicMock()
        mock_client.messages.create.return_value = make_mock_message(VALID_LLM_RESPONSE)
        mock_anthropic_class.return_value = mock_client

        # Premier appel : cache miss
        parse_procedure_text_llm("Texte identique")
        # Second appel : devrait hit le cache
        parse_procedure_text_llm("Texte identique")

        # L'API n'a été appelée qu'une seule fois
        self.assertEqual(mock_client.messages.create.call_count, 1)

    @patch("anthropic.Anthropic")
    def test_different_texts_miss_cache(self, mock_anthropic_class):
        """Deux textes différents → deux appels API."""
        from procedures.services.llm_parser import parse_procedure_text_llm

        mock_client = MagicMock()
        mock_client.messages.create.return_value = make_mock_message(VALID_LLM_RESPONSE)
        mock_anthropic_class.return_value = mock_client

        parse_procedure_text_llm("Texte A")
        parse_procedure_text_llm("Texte B")

        self.assertEqual(mock_client.messages.create.call_count, 2)

    @patch("anthropic.Anthropic")
    def test_force_refresh_bypasses_cache(self, mock_anthropic_class):
        """force_refresh=True doit ignorer le cache."""
        from procedures.services.llm_parser import parse_procedure_text_llm

        mock_client = MagicMock()
        mock_client.messages.create.return_value = make_mock_message(VALID_LLM_RESPONSE)
        mock_anthropic_class.return_value = mock_client

        parse_procedure_text_llm("Même texte")
        parse_procedure_text_llm("Même texte", force_refresh=True)

        self.assertEqual(mock_client.messages.create.call_count, 2)

    @patch("anthropic.Anthropic")
    def test_cache_hit_is_logged(self, mock_anthropic_class):
        """Un hit de cache doit être loggué avec cache_hit=True."""
        from procedures.services.llm_parser import parse_procedure_text_llm
        from procedures.models import LLMCallLog

        mock_client = MagicMock()
        mock_client.messages.create.return_value = make_mock_message(VALID_LLM_RESPONSE)
        mock_anthropic_class.return_value = mock_client

        parse_procedure_text_llm("Un texte")     # cache miss
        parse_procedure_text_llm("Un texte")     # cache hit

        logs = LLMCallLog.objects.order_by("created_at")
        self.assertEqual(logs.count(), 2)
        self.assertFalse(logs[0].cache_hit)
        self.assertTrue(logs[1].cache_hit)


@override_settings(
    ANTHROPIC_API_KEY="test-fake-key-for-tests",
    LLM_PARSER_MODEL="claude-haiku-4-5-20251001",
)
class LLMParserFallbackTests(TestCase):
    """Vérifie le comportement de fallback sur spaCy en cas d'erreur."""

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    @patch("procedures.services.llm_parser._fallback_to_rules")
    @patch("anthropic.Anthropic")
    def test_api_error_triggers_fallback(self, mock_anthropic_class, mock_fallback):
        """Une exception API doit déclencher le fallback."""
        from procedures.services.llm_parser import parse_procedure_text_llm

        # Le client lève une exception à chaque tentative
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API down")
        mock_anthropic_class.return_value = mock_client

        mock_fallback.return_value = []

        parse_procedure_text_llm("Un texte")

        mock_fallback.assert_called_once()

    @patch("procedures.services.llm_parser._fallback_to_rules")
    @patch("anthropic.Anthropic")
    def test_invalid_json_triggers_fallback(self, mock_anthropic_class, mock_fallback):
        """Un JSON invalide dans la réponse doit déclencher le fallback."""
        from procedures.services.llm_parser import parse_procedure_text_llm

        # Le mock retourne un contenu qui n'est pas du JSON
        block = MagicMock()
        block.text = "ceci n'est pas du json"
        message = MagicMock()
        message.content = [block]
        message.usage.input_tokens = 10
        message.usage.output_tokens = 10

        mock_client = MagicMock()
        mock_client.messages.create.return_value = message
        mock_anthropic_class.return_value = mock_client

        mock_fallback.return_value = []

        parse_procedure_text_llm("Un texte")

        mock_fallback.assert_called_once()

    @patch("anthropic.Anthropic")
    def test_api_error_retries_once_before_fallback(self, mock_anthropic_class):
        """L'appel est réessayé 1 fois avant de fallback."""
        from procedures.services.llm_parser import parse_procedure_text_llm

        # Le client lève toujours une exception : on devrait voir 2 appels (1 + 1 retry)
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API down")
        mock_anthropic_class.return_value = mock_client

        with patch("procedures.services.llm_parser._fallback_to_rules", return_value=[]):
            parse_procedure_text_llm("Un texte")

        self.assertEqual(mock_client.messages.create.call_count, 2)

    @patch("procedures.services.llm_parser._fallback_to_rules")
    @patch("anthropic.Anthropic")
    def test_fallback_logged_as_such(self, mock_anthropic_class, mock_fallback):
        """Un fallback doit être loggué avec fallback_used=True."""
        from procedures.services.llm_parser import parse_procedure_text_llm
        from procedures.models import LLMCallLog

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API down")
        mock_anthropic_class.return_value = mock_client
        mock_fallback.return_value = []

        parse_procedure_text_llm("Un texte")

        self.assertEqual(LLMCallLog.objects.count(), 1)
        log = LLMCallLog.objects.first()
        self.assertTrue(log.fallback_used)
        self.assertFalse(log.cache_hit)
        self.assertEqual(log.model, "fallback")


@override_settings(ANTHROPIC_API_KEY="")
class LLMParserMissingKeyTests(TestCase):
    """Quand la clé API est absente, fallback immédiat sans tenter l'appel."""

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    @patch("procedures.services.llm_parser._fallback_to_rules")
    def test_missing_api_key_triggers_fallback(self, mock_fallback):
        from procedures.services.llm_parser import parse_procedure_text_llm

        mock_fallback.return_value = []
        parse_procedure_text_llm("Un texte")

        # Le fallback a été appelé
        mock_fallback.assert_called_once()


@override_settings(
    ANTHROPIC_API_KEY="test-fake-key-for-tests",
    LLM_PARSER_MODEL="claude-haiku-4-5-20251001",
)
class LLMParserValidationTests(TestCase):
    """Tests de la fonction de validation du JSON retourné."""

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    @patch("anthropic.Anthropic")
    def test_step_without_required_fields_is_skipped(self, mock_anthropic_class):
        """Une étape sans order/title/action_verb est ignorée."""
        from procedures.services.llm_parser import parse_procedure_text_llm

        incomplete = {
            "steps": [
                {"order": 1, "title": "Valide", "action_verb": "valider"},   # OK
                {"title": "Sans order"},                                      # Skip : pas d'order
                {"order": 2},                                                 # Skip : pas de title ni de verb
            ]
        }
        mock_client = MagicMock()
        mock_client.messages.create.return_value = make_mock_message(incomplete)
        mock_anthropic_class.return_value = mock_client

        steps = parse_procedure_text_llm("Texte")
        self.assertEqual(len(steps), 1)

    @patch("anthropic.Anthropic")
    def test_invalid_frequency_normalized_to_empty(self, mock_anthropic_class):
        """Une fréquence non reconnue est ramenée à chaîne vide."""
        from procedures.services.llm_parser import parse_procedure_text_llm

        response = {
            "steps": [
                {
                    "order": 1, "title": "X", "action_verb": "faire",
                    "frequency": "invented_frequency", "is_recurring": True,
                }
            ]
        }
        mock_client = MagicMock()
        mock_client.messages.create.return_value = make_mock_message(response)
        mock_anthropic_class.return_value = mock_client

        steps = parse_procedure_text_llm("Texte")
        self.assertEqual(steps[0].frequency, "")

    @patch("anthropic.Anthropic")
    def test_automation_score_out_of_range_is_clamped(self, mock_anthropic_class):
        """Un automation_score > 1.0 ou < 0.0 est ramené dans [0.0, 1.0]."""
        from procedures.services.llm_parser import parse_procedure_text_llm

        response = {
            "steps": [
                {"order": 1, "title": "A", "action_verb": "x", "automation_score": 2.5},
                {"order": 2, "title": "B", "action_verb": "y", "automation_score": -3.0},
            ]
        }
        mock_client = MagicMock()
        mock_client.messages.create.return_value = make_mock_message(response)
        mock_anthropic_class.return_value = mock_client

        steps = parse_procedure_text_llm("Texte")
        self.assertEqual(steps[0].automation_score, 1.0)
        self.assertEqual(steps[1].automation_score, 0.0)
