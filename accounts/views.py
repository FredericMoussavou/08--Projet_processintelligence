import json
import re
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from organizations.models import Organization, Membership


def _get_tokens(user):
    refresh = RefreshToken.for_user(user)
    return {
        'access' : str(refresh.access_token),
        'refresh': str(refresh),
    }


@csrf_exempt
def register(request):
    """
    Inscription + création organisation.
    POST /api/auth/register/
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode non autorisée'}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON invalide'}, status=400)

    username = data.get('username', '').strip()
    email    = data.get('email', '').strip()
    password = data.get('password', '')
    org_name = data.get('organization_name', '').strip()
    sector   = data.get('sector', 'other')

    if not all([username, email, password, org_name]):
        return JsonResponse(
            {'error': 'Champs obligatoires : username, email, password, organization_name'},
            status=400
        )
    if len(password) < 8:
        return JsonResponse({'error': 'Mot de passe trop court — minimum 8 caractères'}, status=400)
    if User.objects.filter(username=username).exists():
        return JsonResponse({'error': "Ce nom d'utilisateur est déjà pris"}, status=400)
    if User.objects.filter(email=email).exists():
        return JsonResponse({'error': 'Cet email est déjà utilisé'}, status=400)

    user = User.objects.create_user(username=username, email=email, password=password)

    # Slug unique
    slug      = re.sub(r'[^a-z0-9]+', '-', org_name.lower()).strip('-')
    base_slug = slug
    counter   = 1
    while Organization.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1

    organization = Organization.objects.create(name=org_name, slug=slug, sector=sector)
    Membership.objects.create(user=user, organization=organization, role=Membership.ROLE_ADMIN)

    return JsonResponse({
        'success'     : True,
        'user'        : {'id': user.id, 'username': user.username, 'email': user.email},
        'organization': {'id': organization.id, 'name': organization.name, 'slug': organization.slug},
        'tokens'      : _get_tokens(user),
        'message'     : 'Compte créé avec succès',
    }, status=201)


@csrf_exempt
def login_view(request):
    """
    Connexion.
    POST /api/auth/login/
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode non autorisée'}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON invalide'}, status=400)

    username = data.get('username', '')
    password = data.get('password', '')

    try:
        user = User.objects.get(username=username)
        if not user.check_password(password):
            raise ValueError
    except (User.DoesNotExist, ValueError):
        return JsonResponse({'error': 'Identifiants invalides'}, status=401)

    if not user.is_active:
        return JsonResponse({'error': 'Compte désactivé'}, status=403)

    memberships = Membership.objects.filter(user=user).select_related('organization')

    return JsonResponse({
        'success'      : True,
        'user'         : {'id': user.id, 'username': user.username, 'email': user.email},
        'organizations': [
            {
                'id'    : m.organization.id,
                'name'  : m.organization.name,
                'slug'  : m.organization.slug,
                'role'  : m.role,
                'sector': m.organization.sector,
            }
            for m in memberships
        ],
        'tokens': _get_tokens(user),
    })


@csrf_exempt
def refresh_token(request):
    """
    Rafraîchit le token d'accès.
    POST /api/auth/refresh/
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode non autorisée'}, status=405)

    try:
        data    = json.loads(request.body)
        refresh = data.get('refresh', '')
        token   = RefreshToken(refresh)
        return JsonResponse({'access': str(token.access_token)})
    except (json.JSONDecodeError, TokenError):
        return JsonResponse({'error': 'Token invalide ou expiré'}, status=401)


def me(request):
    """
    Infos de l'utilisateur connecté.
    GET /api/auth/me/
    """
    # Compatible avec l'authentification JWT via middleware
    user = getattr(request, 'user', None)
    
    if user is None or not user.is_authenticated:
        # Tentative d'authentification directe via JWT
        from rest_framework_simplejwt.authentication import JWTAuthentication
        from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
        try:
            jwt_auth = JWTAuthentication()
            result = jwt_auth.authenticate(request)
            if result:
                user = result[0]
            else:
                return JsonResponse({'error': 'Non authentifié'}, status=401)
        except (InvalidToken, TokenError):
            return JsonResponse({'error': 'Token invalide ou expiré'}, status=401)

    memberships = Membership.objects.filter(user=user).select_related('organization')

    return JsonResponse({
        'user': {
            'id'      : user.id,
            'username': user.username,
            'email'   : user.email,
        },
        'organizations': [
            {
                'id'    : m.organization.id,
                'name'  : m.organization.name,
                'slug'  : m.organization.slug,
                'role'  : m.role,
                'sector': m.organization.sector,
            }
            for m in memberships
        ]
    })