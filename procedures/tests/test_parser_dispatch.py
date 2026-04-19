"""
Tests unitaires du dispatcher.

Valide que la règle de sélection spaCy/Claude est correcte dans toutes
les combinaisons (endpoint public, kill switch, plan, expiration, etc.).

Lance avec :
    python manage.py test procedures.tests.test_parser_dispatch -v 2
"""

from unittest.mock import patch
from django.test import TestCase, override_settings
from django.utils import timezone
from datetime import timedelta

from organizations.models import Organization
from procedures.services.parser_dispatch import should_use_llm, ENGINE_SPACY, ENGINE_CLAUDE


@override_settings(
    LLM_PARSER_ENABLED=True,
    ANTHROPIC_API_KEY="test-fake-key-for-tests",
)
class DispatcherDecisionTests(TestCase):
    """
    Tests de la fonction should_use_llm.

    On définit LLM_PARSER_ENABLED=True et une clé API factice via @override_settings
    pour simuler un environnement configuré. Les cas où ces valeurs sont absentes
    sont testés séparément plus bas.
    """

    def setUp(self):
        self.org_free = Organization.objects.create(
            name="Free Corp", slug="free-corp", plan="free",
        )
        self.org_pro = Organization.objects.create(
            name="Pro Corp", slug="pro-corp", plan="pro",
            plan_started_at=timezone.now(),
        )
        self.org_biz = Organization.objects.create(
            name="Biz Corp", slug="biz-corp", plan="business",
            plan_started_at=timezone.now(),
        )
        # Organisation Pro avec plan expiré
        self.org_pro_expired = Organization.objects.create(
            name="Expired Pro", slug="expired-pro", plan="pro",
            plan_started_at=timezone.now() - timedelta(days=365),
            plan_expires_at=timezone.now() - timedelta(days=1),
        )

    # ------------------------------------------------------------------
    # Règle 1 : endpoint public -> spaCy toujours
    # ------------------------------------------------------------------

    def test_public_endpoint_forces_spacy_even_with_pro_org(self):
        """Diagnostic Express avec une org Pro doit quand même utiliser spaCy."""
        self.assertFalse(should_use_llm(organization=self.org_pro, is_public_endpoint=True))

    def test_public_endpoint_forces_spacy_with_no_org(self):
        self.assertFalse(should_use_llm(organization=None, is_public_endpoint=True))

    def test_public_endpoint_forces_spacy_with_business(self):
        self.assertFalse(should_use_llm(organization=self.org_biz, is_public_endpoint=True))

    # ------------------------------------------------------------------
    # Règle 4 : organisation absente -> spaCy
    # ------------------------------------------------------------------

    def test_no_org_uses_spacy(self):
        self.assertFalse(should_use_llm(organization=None))

    # ------------------------------------------------------------------
    # Règle 5 : selon le plan
    # ------------------------------------------------------------------

    def test_free_org_uses_spacy(self):
        self.assertFalse(should_use_llm(organization=self.org_free))

    def test_pro_org_uses_claude(self):
        self.assertTrue(should_use_llm(organization=self.org_pro))

    def test_business_org_uses_claude(self):
        self.assertTrue(should_use_llm(organization=self.org_biz))

    def test_expired_pro_falls_back_to_spacy(self):
        """Un plan Pro expiré doit perdre l'accès au LLM."""
        self.assertFalse(should_use_llm(organization=self.org_pro_expired))


class DispatcherConfigTests(TestCase):
    """
    Tests des règles de configuration globale : kill switch, clé API absente.
    """

    def setUp(self):
        self.org_pro = Organization.objects.create(
            name="Pro Corp", slug="pro-corp-config", plan="pro",
            plan_started_at=timezone.now(),
        )

    @override_settings(LLM_PARSER_ENABLED=False, ANTHROPIC_API_KEY="test-key")
    def test_kill_switch_forces_spacy(self):
        """
        LLM_PARSER_ENABLED=False doit forcer spaCy même pour une org Pro.
        Utile pour désactiver rapidement en cas d'incident avec l'API Anthropic.
        """
        self.assertFalse(should_use_llm(organization=self.org_pro))

    @override_settings(LLM_PARSER_ENABLED=True, ANTHROPIC_API_KEY="")
    def test_missing_api_key_falls_back_to_spacy(self):
        """
        Clé API absente doit fallback sur spaCy plutôt que crasher.
        Cas typique : oubli de config en prod.
        """
        self.assertFalse(should_use_llm(organization=self.org_pro))

    @override_settings(LLM_PARSER_ENABLED=True, ANTHROPIC_API_KEY="ok")
    def test_both_configured_and_pro_uses_claude(self):
        """Sanity check : avec tout bien configuré + org Pro, on utilise Claude."""
        self.assertTrue(should_use_llm(organization=self.org_pro))


@override_settings(
    LLM_PARSER_ENABLED=True,
    ANTHROPIC_API_KEY="test-fake-key-for-tests",
)
class ParseIntegrationTests(TestCase):
    """
    Tests de la fonction parse() qui est le point d'entrée public.

    On mocke les deux parsers (spaCy et Claude) pour valider la sélection
    sans déclencher de vrais appels API ni charger spaCy.
    """

    def setUp(self):
        self.org_free = Organization.objects.create(
            name="Free", slug="free-parse", plan="free",
        )
        self.org_pro = Organization.objects.create(
            name="Pro", slug="pro-parse", plan="pro",
            plan_started_at=timezone.now(),
        )

    @patch("procedures.services.parser_dispatch._parse_with_spacy")
    def test_free_org_calls_spacy(self, mock_spacy):
        from procedures.services.parser_dispatch import parse
        mock_spacy.return_value = []
        steps, engine = parse("un texte", organization=self.org_free)
        mock_spacy.assert_called_once()
        self.assertEqual(engine, ENGINE_SPACY)

    @patch("procedures.services.parser_dispatch._parse_with_claude")
    def test_pro_org_calls_claude(self, mock_claude):
        from procedures.services.parser_dispatch import parse
        mock_claude.return_value = []
        steps, engine = parse("un texte", organization=self.org_pro)
        mock_claude.assert_called_once()
        self.assertEqual(engine, ENGINE_CLAUDE)

    @patch("procedures.services.parser_dispatch._parse_with_spacy")
    def test_public_endpoint_calls_spacy_even_with_pro(self, mock_spacy):
        from procedures.services.parser_dispatch import parse
        mock_spacy.return_value = []
        steps, engine = parse("un texte", organization=self.org_pro, is_public_endpoint=True)
        mock_spacy.assert_called_once()
        self.assertEqual(engine, ENGINE_SPACY)
