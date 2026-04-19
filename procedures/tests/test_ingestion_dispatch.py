"""
Tests d'intégration de procedures/services/ingestion.py.

Ces tests vérifient que la logique de dispatching (spaCy / Claude) est
correctement appelée depuis les fonctions ingest_*, avec les bons paramètres
selon le plan de l'organisation et le quota mensuel.

Utilise des mocks pour ne pas appeler l'API Claude ni charger spaCy.

Lance avec :
    python manage.py test procedures.tests.test_ingestion_dispatch -v 2
"""

from unittest.mock import patch, MagicMock
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone

from organizations.models import Organization
from procedures.services import ingestion


class _FakeParsedStep:
    """Fake ParsedStep minimal pour les tests — évite de charger parser.py."""
    def __init__(self, order=1, title="Étape", action_verb="faire"):
        self.order = order
        self.title = title
        self.action_verb = action_verb
        self.actor_role = "Manager"
        self.tool_used = ""
        self.has_condition = False
        self.is_recurring = False
        self.output_type = "none"
        self.automation_score = 0.5


@override_settings(
    LLM_PARSER_ENABLED=True,
    ANTHROPIC_API_KEY="fake-key",
)
class IngestDispatchTests(TestCase):
    """
    Vérifie que ingest_text() appelle le bon moteur selon le plan.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="alice", email="alice@example.com", password="x"
        )
        self.org_free = Organization.objects.create(
            name="Free Inc", slug="free-inc", plan="free",
        )
        self.org_pro = Organization.objects.create(
            name="Pro Inc", slug="pro-inc", plan="pro",
            plan_started_at=timezone.now(),
        )

    @patch("procedures.services.ingestion.parser_dispatch.parse")
    @patch("procedures.services.ingestion._create_procedure_and_steps")
    def test_free_org_triggers_spacy_engine(self, mock_create, mock_parse):
        """Org Free → le dispatcher renvoie engine='spacy'."""
        mock_parse.return_value = ([_FakeParsedStep()], "spacy")
        mock_create.return_value = {'success': True, 'engine_used': 'spacy'}

        ingestion.ingest_text(
            text="Test", title="T", service="S",
            organization=self.org_free, owner=self.user,
            apply_masking=False, is_public_endpoint=False,
        )

        # Le dispatcher a été appelé avec l'org Free
        mock_parse.assert_called_once()
        call_kwargs = mock_parse.call_args.kwargs
        self.assertEqual(call_kwargs['organization'], self.org_free)

        # _create_procedure_and_steps a reçu engine='spacy'
        create_kwargs = mock_create.call_args.kwargs
        self.assertEqual(create_kwargs['engine_used'], 'spacy')

    @patch("procedures.services.ingestion.parser_dispatch.parse")
    @patch("procedures.services.ingestion._create_procedure_and_steps")
    def test_pro_org_triggers_claude_engine(self, mock_create, mock_parse):
        """Org Pro → le dispatcher renvoie engine='claude'."""
        mock_parse.return_value = ([_FakeParsedStep()], "claude")
        mock_create.return_value = {'success': True, 'engine_used': 'claude'}

        ingestion.ingest_text(
            text="Test", title="T", service="S",
            organization=self.org_pro, owner=self.user,
            apply_masking=False, is_public_endpoint=False,
        )

        create_kwargs = mock_create.call_args.kwargs
        self.assertEqual(create_kwargs['engine_used'], 'claude')

    @patch("procedures.services.ingestion.parser_dispatch.parse")
    @patch("procedures.services.ingestion._create_procedure_and_steps")
    def test_public_endpoint_forces_spacy_even_with_pro(self, mock_create, mock_parse):
        """Diagnostic Express avec org Pro → effective_public=True dans le dispatcher."""
        mock_parse.return_value = ([_FakeParsedStep()], "spacy")
        mock_create.return_value = {'success': True, 'engine_used': 'spacy'}

        ingestion.ingest_text(
            text="Test", title="T", service="S",
            organization=self.org_pro, owner=None,
            apply_masking=False, is_public_endpoint=True,
        )

        # Le dispatcher doit recevoir is_public_endpoint=True
        call_kwargs = mock_parse.call_args.kwargs
        self.assertTrue(call_kwargs['is_public_endpoint'])


@override_settings(
    LLM_PARSER_ENABLED=True,
    ANTHROPIC_API_KEY="fake-key",
)
class QuotaDegradationTests(TestCase):
    """
    Vérifie la dégradation silencieuse quand le quota mensuel est atteint.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="bob", email="bob@x.com", password="x")
        self.org_pro = Organization.objects.create(
            name="Pro Inc", slug="pro-quota", plan="pro",
            plan_started_at=timezone.now(),
        )

    @patch("procedures.services.ingestion.parser_dispatch.parse")
    @patch("procedures.services.ingestion._create_procedure_and_steps")
    def test_quota_not_reached_allows_claude(self, mock_create, mock_parse):
        """Sous le quota → le dispatcher peut appeler Claude."""
        mock_parse.return_value = ([_FakeParsedStep()], "claude")
        mock_create.return_value = {'success': True}

        ingestion.ingest_text(
            text="Test", title="T", service="S",
            organization=self.org_pro, owner=self.user,
            apply_masking=False, is_public_endpoint=False,
        )

        # effective_public doit être False (org Pro, quota OK)
        call_kwargs = mock_parse.call_args.kwargs
        self.assertFalse(call_kwargs['is_public_endpoint'])

    @patch("procedures.services.ingestion.parser_dispatch.parse")
    @patch("procedures.services.ingestion._create_procedure_and_steps")
    def test_quota_reached_forces_spacy_silently(self, mock_create, mock_parse):
        """Quota atteint → dégradation sur spaCy en forçant effective_public=True."""
        from procedures.models import MonthlyUsage

        # On simule un quota atteint (limite Pro = 500)
        now = timezone.now()
        MonthlyUsage.objects.create(
            organization=self.org_pro,
            year=now.year, month=now.month,
            analyses_count=500,   # = limite Pro
        )

        mock_parse.return_value = ([_FakeParsedStep()], "spacy")
        mock_create.return_value = {'success': True}

        result = ingestion.ingest_text(
            text="Test", title="T", service="S",
            organization=self.org_pro, owner=self.user,
            apply_masking=False, is_public_endpoint=False,
        )

        # effective_public doit être True (quota atteint → dégradation)
        call_kwargs = mock_parse.call_args.kwargs
        self.assertTrue(call_kwargs['is_public_endpoint'])

        # quota_info doit refléter le quota atteint
        create_kwargs = mock_create.call_args.kwargs
        self.assertTrue(create_kwargs['quota_info']['quota_reached'])
        self.assertEqual(create_kwargs['quota_info']['analyses_this_month'], 500)
        self.assertEqual(create_kwargs['quota_info']['monthly_limit'], 500)


@override_settings(
    LLM_PARSER_ENABLED=True,
    ANTHROPIC_API_KEY="fake-key",
)
class MaskingPropagationTests(TestCase):
    """
    Vérifie que le flag apply_masking est bien propagé au dispatcher.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="carol", email="c@x.com", password="x")
        self.org = Organization.objects.create(
            name="X", slug="mask-test", plan="pro",
            plan_started_at=timezone.now(),
        )

    @patch("procedures.services.ingestion.mask_text")
    @patch("procedures.services.ingestion.parser_dispatch.parse")
    @patch("procedures.services.ingestion._create_procedure_and_steps")
    def test_apply_masking_true_calls_masker(self, mock_create, mock_parse, mock_mask):
        """apply_masking=True doit appeler mask_text avant le dispatcher."""
        mock_mask.return_value = ("texte masqué", {"Jean": "PER_1"})
        mock_parse.return_value = ([_FakeParsedStep()], "claude")
        mock_create.return_value = {'success': True}

        ingestion.ingest_text(
            text="Jean valide le dossier", title="T", service="S",
            organization=self.org, owner=self.user,
            apply_masking=True, is_public_endpoint=False,
        )

        mock_mask.assert_called_once_with("Jean valide le dossier")
        # Le dispatcher doit recevoir le texte masqué
        call_kwargs = mock_parse.call_args.kwargs
        self.assertEqual(call_kwargs['text'], "texte masqué")
        self.assertTrue(call_kwargs['apply_masking'])

    @patch("procedures.services.ingestion.mask_text")
    @patch("procedures.services.ingestion.parser_dispatch.parse")
    @patch("procedures.services.ingestion._create_procedure_and_steps")
    def test_apply_masking_false_skips_masker(self, mock_create, mock_parse, mock_mask):
        """apply_masking=False NE doit PAS appeler mask_text."""
        mock_parse.return_value = ([_FakeParsedStep()], "claude")
        mock_create.return_value = {'success': True}

        ingestion.ingest_text(
            text="Jean valide", title="T", service="S",
            organization=self.org, owner=self.user,
            apply_masking=False, is_public_endpoint=False,
        )

        mock_mask.assert_not_called()
        # Le dispatcher reçoit le texte original
        call_kwargs = mock_parse.call_args.kwargs
        self.assertEqual(call_kwargs['text'], "Jean valide")
        self.assertFalse(call_kwargs['apply_masking'])


@override_settings(LLM_PARSER_ENABLED=False)
class BackwardsCompatibilityTests(TestCase):
    """
    Vérifie que la rétrocompatibilité est préservée quand LLM_PARSER_ENABLED=False.
    Dans ce cas, spaCy doit être utilisé partout, comportement identique à avant.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="dave", email="d@x.com", password="x")
        self.org_pro = Organization.objects.create(
            name="Pro", slug="compat-pro", plan="pro",
            plan_started_at=timezone.now(),
        )

    @patch("procedures.services.ingestion.parser_dispatch.parse")
    @patch("procedures.services.ingestion._create_procedure_and_steps")
    def test_llm_disabled_always_uses_spacy_even_for_pro(self, mock_create, mock_parse):
        """Kill switch actif → spaCy partout, même pour org Pro."""
        mock_parse.return_value = ([_FakeParsedStep()], "spacy")
        mock_create.return_value = {'success': True, 'engine_used': 'spacy'}

        ingestion.ingest_text(
            text="Test", title="T", service="S",
            organization=self.org_pro, owner=self.user,
            apply_masking=False, is_public_endpoint=False,
        )

        # Le dispatcher décide en interne — il verra LLM_PARSER_ENABLED=False
        # et renverra spacy. On vérifie juste que engine='spacy' est bien propagé.
        create_kwargs = mock_create.call_args.kwargs
        self.assertEqual(create_kwargs['engine_used'], 'spacy')
