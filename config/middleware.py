from django.http import JsonResponse
from django.core.cache import cache
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
import time


class JWTAuthMiddleware:
    """
    Middleware JWT + Rate Limiting intégré.
    Authentifie les requêtes et limite les appels par IP.
    """

    PUBLIC_PATHS = [
        '/api/auth/login/',
        '/api/auth/register/',
        '/api/auth/refresh/',
        '/admin/',
    ]

    AUTHENTICATED_PATHS = [
        '/api/auth/me/',
    ]

    DIAGNOSTIC_PATHS = [
        '/api/procedures/ingest/',
        '/api/procedures/template/csv/',
        '/api/procedures/rules/',
    ]

    # Limites par endpoint (requêtes / minute)
    RATE_LIMITS = {
        '/api/procedures/ingest/'          : 20,
        '/api/procedures/change-requests/' : 10,
        '/api/auth/login/'                 : 5,
        '/api/auth/register/'              : 3,
    }
    DEFAULT_RATE = 60

    def __init__(self, get_response):
        self.get_response = get_response
        self.jwt_auth     = JWTAuthentication()

    def __call__(self, request):
            path = request.path

            # Rate limiting sur toutes les routes POST
            if request.method == 'POST':
                rate_result = self._check_rate_limit(request, path)
                if rate_result:
                    return rate_result

            # Routes publiques — pas d'auth
            if any(path.startswith(p) for p in self.PUBLIC_PATHS):
                return self.get_response(request)

            # Routes auth obligatoire dans le namespace /auth/
            if any(path.startswith(p) for p in self.AUTHENTICATED_PATHS):
                if not self._try_authenticate(request):
                    return JsonResponse(
                        {'error': 'Authentification requise'},
                        status=401
                    )
                return self.get_response(request)

            # Routes Diagnostic Express — auth optionnelle
            if any(path.startswith(p) for p in self.DIAGNOSTIC_PATHS):
                self._try_authenticate(request)
                return self.get_response(request)

            # Toutes les autres routes — auth obligatoire
            if not self._try_authenticate(request):
                return JsonResponse(
                    {'error': 'Authentification requise — fournissez un token JWT valide'},
                    status=401
                )

            return self.get_response(request)

    def _check_rate_limit(self, request, path) -> JsonResponse | None:
        """
        Vérifie la limite de taux par IP.
        Retourne une JsonResponse 429 si la limite est dépassée.
        """
        ip       = self._get_client_ip(request)
        limit    = self._get_limit_for_path(path)
        cache_key = f"rl:{ip}:{path}"

        # Récupère le compteur actuel
        try:
            data = cache.get(cache_key)
            if data is None:
                cache.set(cache_key, {'count': 1, 'reset': time.time() + 60}, 60)
                return None

            if time.time() > data['reset']:
                cache.set(cache_key, {'count': 1, 'reset': time.time() + 60}, 60)
                return None

            if data['count'] >= limit:
                return JsonResponse(
                    {
                        'error': 'Trop de requêtes — réessayez dans une minute',
                        'limit': limit,
                        'reset': int(data['reset'] - time.time()),
                    },
                    status=429
                )

            data['count'] += 1
            cache.set(cache_key, data, int(data['reset'] - time.time()))
        except Exception:
            # Si le cache est indisponible, on laisse passer
            pass

        return None

    def _get_limit_for_path(self, path) -> int:
        for route, limit in self.RATE_LIMITS.items():
            if path.startswith(route):
                return limit
        return self.DEFAULT_RATE

    def _get_client_ip(self, request) -> str:
        x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded:
            return x_forwarded.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '0.0.0.0')

    def _try_authenticate(self, request) -> bool:
        try:
            result = self.jwt_auth.authenticate(request)
            if result:
                request.user = result[0]
                return True
        except (InvalidToken, TokenError):
            pass
        return False