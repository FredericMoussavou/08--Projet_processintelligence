"""
Tests des endpoints GET /api/organizations/<id>/plan/ et /usage/.

IMPORTANT : ces endpoints passent par le middleware JWTAuthMiddleware qui
exige un vrai token JWT dans l'en-tête Authorization. Ces tests utilisent
donc djangorestframework-simplejwt pour générer de vrais tokens.

Lance avec :
    python manage.py test organizations.tests.test_plan_usage_views -v 2
"""

import json
from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from organizations.models import Organization, Membership


# ─────────────────────────────────────────────
# Helper : client authentifié avec JWT
# ─────────────────────────────────────────────

def _jwt_client_for(user):
    """
    Retourne un Client Django avec un vrai JWT access token dans l'en-tête
    Authorization. Compatible avec le middleware JWTAuthMiddleware.

    Pattern classique pour tester des vues derrière un middleware JWT.
    """
    refresh = RefreshToken.for_user(user)
    access_token = str(refresh.access_token)

    client = Client()
    client.defaults['HTTP_AUTHORIZATION'] = f'Bearer {access_token}'
    return client


# ─────────────────────────────────────────────
# Tests : GET /api/organizations/<id>/plan/
# ─────────────────────────────────────────────

class GetOrganizationPlanTests(TestCase):

    def setUp(self):
        self.org_pro = Organization.objects.create(
            name="Pro Co", slug="pro-co", plan="pro",
            plan_started_at=timezone.now(),
        )
        self.org_free = Organization.objects.create(
            name="Free Co", slug="free-co", plan="free",
        )
        self.org_biz = Organization.objects.create(
            name="Biz Co", slug="biz-co", plan="business",
        )

        # Membre de org_pro
        self.member = User.objects.create_user(
            username="member", email="m@x.com", password="pwd",
        )
        Membership.objects.create(
            user=self.member, organization=self.org_pro, role="manager",
        )

        # Outsider (membre d'aucune org)
        self.outsider = User.objects.create_user(
            username="outsider", email="o@x.com", password="pwd",
        )

    def test_member_can_view_plan(self):
        client = _jwt_client_for(self.member)
        response = client.get(f'/api/organizations/{self.org_pro.id}/plan/')
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data['plan']['id'], 'pro')
        self.assertEqual(data['plan']['name'], 'Pro')
        self.assertTrue(data['plan']['is_paid'])
        self.assertTrue(data['plan']['features']['llm_enabled'])
        self.assertTrue(data['plan']['features']['export_bpmn'])
        self.assertEqual(data['plan']['limits']['procedures'], 100)

    def test_outsider_cannot_view_plan(self):
        """Un utilisateur non-membre doit recevoir 403."""
        client = _jwt_client_for(self.outsider)
        response = client.get(f'/api/organizations/{self.org_pro.id}/plan/')
        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_cannot_view_plan(self):
        """
        Un anonyme (sans token JWT) doit être bloqué par le middleware
        avec un 401 'Authentification requise', PAS par notre vue en 403.
        C'est normal : le middleware intercepte avant notre vue.
        """
        client = Client()   # sans Authorization
        response = client.get(f'/api/organizations/{self.org_pro.id}/plan/')
        self.assertEqual(response.status_code, 401)

    def test_nonexistent_org_returns_404(self):
        client = _jwt_client_for(self.member)
        response = client.get('/api/organizations/99999/plan/')
        self.assertEqual(response.status_code, 404)

    def test_free_plan_does_not_expose_llm(self):
        """Le plan Free doit retourner llm_enabled=False."""
        Membership.objects.create(
            user=self.member, organization=self.org_free, role="viewer",
        )
        client = _jwt_client_for(self.member)
        response = client.get(f'/api/organizations/{self.org_free.id}/plan/')
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data['plan']['id'], 'free')
        self.assertFalse(data['plan']['is_paid'])
        self.assertFalse(data['plan']['features']['llm_enabled'])
        self.assertFalse(data['plan']['features']['export_bpmn'])

    def test_business_plan_has_sso(self):
        Membership.objects.create(
            user=self.member, organization=self.org_biz, role="admin",
        )
        client = _jwt_client_for(self.member)
        response = client.get(f'/api/organizations/{self.org_biz.id}/plan/')
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data['plan']['id'], 'business')
        self.assertTrue(data['plan']['features']['sso'])
        self.assertTrue(data['plan']['features']['custom_theme'])
        self.assertIsNone(data['plan']['limits']['procedures'])   # illimité


# ─────────────────────────────────────────────
# Tests : GET /api/organizations/<id>/usage/
# ─────────────────────────────────────────────

class GetOrganizationUsageTests(TestCase):

    def setUp(self):
        self.org_pro = Organization.objects.create(
            name="Pro Co", slug="pro-co-usage", plan="pro",
            plan_started_at=timezone.now(),
        )
        self.member = User.objects.create_user(
            username="pro-user", email="p@x.com", password="pwd",
        )
        Membership.objects.create(
            user=self.member, organization=self.org_pro, role="manager",
        )
        self.outsider = User.objects.create_user(
            username="out-user", email="o2@x.com", password="pwd",
        )

    def test_member_can_view_usage(self):
        client = _jwt_client_for(self.member)
        response = client.get(f'/api/organizations/{self.org_pro.id}/usage/')
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertIn('analyses', data)
        self.assertIn('procedures', data)
        self.assertIn('users', data)
        self.assertEqual(data['analyses']['count'], 0)
        self.assertEqual(data['analyses']['limit'], 500)
        self.assertFalse(data['analyses']['quota_reached'])

    def test_outsider_cannot_view_usage(self):
        client = _jwt_client_for(self.outsider)
        response = client.get(f'/api/organizations/{self.org_pro.id}/usage/')
        self.assertEqual(response.status_code, 403)

    def test_usage_reflects_current_count(self):
        """Le compteur d'analyses du mois doit refléter MonthlyUsage."""
        from procedures.models import MonthlyUsage
        now = timezone.now()
        MonthlyUsage.objects.create(
            organization=self.org_pro,
            year=now.year, month=now.month,
            analyses_count=42,
        )
        client = _jwt_client_for(self.member)
        response = client.get(f'/api/organizations/{self.org_pro.id}/usage/')
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data['analyses']['count'], 42)
        self.assertEqual(data['analyses']['percentage_used'], 8.4)   # 42/500 * 100
        self.assertFalse(data['analyses']['quota_reached'])

    def test_usage_flags_quota_reached(self):
        """Quand le compteur atteint la limite, quota_reached = True."""
        from procedures.models import MonthlyUsage
        now = timezone.now()
        MonthlyUsage.objects.create(
            organization=self.org_pro,
            year=now.year, month=now.month,
            analyses_count=500,
        )
        client = _jwt_client_for(self.member)
        response = client.get(f'/api/organizations/{self.org_pro.id}/usage/')
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data['analyses']['count'], 500)
        self.assertEqual(data['analyses']['percentage_used'], 100.0)
        self.assertTrue(data['analyses']['quota_reached'])

    def test_business_has_null_limits(self):
        """Business : limites None (illimitées) exposées comme null en JSON."""
        org_biz = Organization.objects.create(
            name="BizU", slug="biz-usage", plan="business",
        )
        Membership.objects.create(
            user=self.member, organization=org_biz, role="admin",
        )
        client = _jwt_client_for(self.member)
        response = client.get(f'/api/organizations/{org_biz.id}/usage/')
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertIsNone(data['analyses']['limit'])
        self.assertEqual(data['analyses']['percentage_used'], 0.0)
        self.assertFalse(data['analyses']['quota_reached'])
