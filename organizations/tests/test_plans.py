"""
Tests unitaires du système de plans.

Lance avec :
    python manage.py test organizations.tests.test_plans

Ou pytest :
    pytest organizations/tests/test_plans.py -v
"""

from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from organizations.models import Organization
from organizations.plans import (
    PLAN_FREE, PLAN_PRO, PLAN_BUSINESS,
    get_plan, is_plan_at_least, get_public_plans,
)


class PlansModuleTests(TestCase):
    """Tests du module plans.py (logique pure, sans DB)."""

    def test_get_plan_known(self):
        self.assertEqual(get_plan(PLAN_FREE)["id"], PLAN_FREE)
        self.assertEqual(get_plan(PLAN_PRO)["id"], PLAN_PRO)
        self.assertEqual(get_plan(PLAN_BUSINESS)["id"], PLAN_BUSINESS)

    def test_get_plan_unknown_falls_back_to_free(self):
        """Un plan invalide doit rendre Free (protection défensive)."""
        self.assertEqual(get_plan("hacker")["id"], PLAN_FREE)
        self.assertEqual(get_plan("")["id"], PLAN_FREE)

    def test_is_plan_at_least(self):
        self.assertTrue(is_plan_at_least(PLAN_FREE, PLAN_FREE))
        self.assertTrue(is_plan_at_least(PLAN_PRO, PLAN_FREE))
        self.assertTrue(is_plan_at_least(PLAN_PRO, PLAN_PRO))
        self.assertTrue(is_plan_at_least(PLAN_BUSINESS, PLAN_PRO))
        self.assertTrue(is_plan_at_least(PLAN_BUSINESS, PLAN_BUSINESS))

        self.assertFalse(is_plan_at_least(PLAN_FREE, PLAN_PRO))
        self.assertFalse(is_plan_at_least(PLAN_PRO, PLAN_BUSINESS))

    def test_is_plan_at_least_unknown_is_safe(self):
        self.assertFalse(is_plan_at_least("unknown", PLAN_FREE))
        self.assertFalse(is_plan_at_least(PLAN_FREE, "unknown"))

    def test_plan_limits_hierarchy(self):
        """Les limites doivent s'élargir avec le niveau du plan."""
        free = get_plan(PLAN_FREE)
        pro = get_plan(PLAN_PRO)
        self.assertGreater(pro["limit_procedures"], free["limit_procedures"])
        self.assertGreater(pro["limit_users"], free["limit_users"])
        self.assertGreater(pro["limit_analyses_per_month"], free["limit_analyses_per_month"])

    def test_llm_model_gating(self):
        """Seuls les plans payants ont un llm_model."""
        self.assertIsNone(get_plan(PLAN_FREE)["llm_model"])
        self.assertIsNotNone(get_plan(PLAN_PRO)["llm_model"])
        self.assertIsNotNone(get_plan(PLAN_BUSINESS)["llm_model"])

    def test_get_public_plans_structure(self):
        plans = get_public_plans()
        self.assertEqual(len(plans), 3)
        for p in plans:
            self.assertIn("id", p)
            self.assertIn("limits", p)
            self.assertIn("features", p)
            # Pas de champs internes exposés
            self.assertNotIn("llm_model", p)


class OrganizationPlanTests(TestCase):
    """Tests des méthodes sur le modèle Organization."""

    def setUp(self):
        self.org_free = Organization.objects.create(
            name="Free Corp", slug="free-corp", plan=PLAN_FREE,
        )
        self.org_pro = Organization.objects.create(
            name="Pro Corp", slug="pro-corp", plan=PLAN_PRO,
            plan_started_at=timezone.now(),
        )
        self.org_biz = Organization.objects.create(
            name="Biz Corp", slug="biz-corp", plan=PLAN_BUSINESS,
            plan_started_at=timezone.now(),
        )

    def test_has_paid_plan(self):
        self.assertFalse(self.org_free.has_paid_plan())
        self.assertTrue(self.org_pro.has_paid_plan())
        self.assertTrue(self.org_biz.has_paid_plan())

    def test_can_use_llm(self):
        self.assertFalse(self.org_free.can_use_llm())
        self.assertTrue(self.org_pro.can_use_llm())
        self.assertTrue(self.org_biz.can_use_llm())

    def test_can_use_llm_respects_expiration(self):
        """Un plan payant expiré ne donne plus accès au LLM."""
        self.org_pro.plan_expires_at = timezone.now() - timedelta(days=1)
        self.org_pro.save()
        self.assertFalse(self.org_pro.can_use_llm())

    def test_can_use_llm_with_future_expiration(self):
        """Un plan payant non expiré donne accès au LLM."""
        self.org_pro.plan_expires_at = timezone.now() + timedelta(days=30)
        self.org_pro.save()
        self.assertTrue(self.org_pro.can_use_llm())

    def test_get_llm_model(self):
        self.assertIsNone(self.org_free.get_llm_model())
        self.assertIn("haiku", self.org_pro.get_llm_model())
        self.assertIn("sonnet", self.org_biz.get_llm_model())

    def test_has_feature(self):
        self.assertFalse(self.org_free.has_feature("export_bpmn"))
        self.assertTrue(self.org_pro.has_feature("export_bpmn"))
        self.assertTrue(self.org_biz.has_feature("export_bpmn"))

        self.assertFalse(self.org_free.has_feature("sso"))
        self.assertFalse(self.org_pro.has_feature("sso"))
        self.assertTrue(self.org_biz.has_feature("sso"))

    def test_limit_for(self):
        self.assertEqual(self.org_free.limit_for("procedures"), 5)
        self.assertEqual(self.org_pro.limit_for("procedures"), 100)
        self.assertIsNone(self.org_biz.limit_for("procedures"))

    def test_can_analyze_this_month_under_limit(self):
        """Avec 0 analyses, une org free peut analyser."""
        allowed, current, limit = self.org_free.can_analyze_this_month()
        self.assertTrue(allowed)
        self.assertEqual(current, 0)
        self.assertEqual(limit, 10)

    def test_can_analyze_this_month_at_limit(self):
        """À la limite exacte, on refuse."""
        from procedures.models import MonthlyUsage
        now = timezone.now()
        MonthlyUsage.objects.create(
            organization=self.org_free,
            year=now.year, month=now.month,
            analyses_count=10,   # = limite Free
        )
        allowed, current, limit = self.org_free.can_analyze_this_month()
        self.assertFalse(allowed)
        self.assertEqual(current, 10)
        self.assertEqual(limit, 10)

    def test_can_analyze_this_month_business_unlimited(self):
        """Business : toujours autorisé."""
        allowed, current, limit = self.org_biz.can_analyze_this_month()
        self.assertTrue(allowed)
        self.assertIsNone(limit)

    def test_increment_monthly_analyses_creates_record(self):
        """Le premier increment crée le record."""
        from procedures.models import MonthlyUsage
        self.assertEqual(MonthlyUsage.objects.count(), 0)
        self.org_pro.increment_monthly_analyses()
        self.assertEqual(MonthlyUsage.objects.count(), 1)
        self.assertEqual(self.org_pro.get_monthly_analyses_count(), 1)

    def test_increment_monthly_analyses_multiple_times(self):
        for _ in range(5):
            self.org_pro.increment_monthly_analyses()
        self.assertEqual(self.org_pro.get_monthly_analyses_count(), 5)
