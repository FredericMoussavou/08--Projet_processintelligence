"""
Service de gestion des consentements RGPD.

Enregistre les consentements utilisateurs à envoyer du texte non-masqué
au LLM externe (Anthropic). Utilisé par la vue d'ingestion et le dispatcher.

Utilisation typique dans une vue :

    from procedures.services.consent import record_masking_consent

    if not apply_masking:
        record_masking_consent(
            request=request,
            endpoint=request.path,
            consent_text=request.data.get('masking_consent_text', ''),
        )
"""

import hashlib
import logging

logger = logging.getLogger(__name__)


# Texte exact que l'utilisateur doit accepter pour désactiver le masquage.
# Les mots-clés "Anthropic" et "États-Unis" doivent y apparaître (vérifié en fonction
# de validation) pour garantir que l'utilisateur a bien été informé du transfert.
DEFAULT_CONSENT_TEXT = (
    "En désactivant le masquage des données personnelles, je consens "
    "au transfert de mon texte à Anthropic (États-Unis) pour analyse. "
    "Je certifie que ce texte ne contient pas de données personnelles "
    "réelles ou que j'ai le droit de les partager."
)

# Mots-clés obligatoires dans le texte de consentement.
# Si le frontend envoie autre chose, on fallback sur DEFAULT_CONSENT_TEXT
# et on log un warning (indice d'un frontend mal configuré ou d'une tentative
# malveillante de contourner l'information).
REQUIRED_CONSENT_KEYWORDS = ("Anthropic", "États-Unis")


def _anonymize_ip(ip: str) -> tuple:
    """
    Sépare une IP en partie anonymisée + dernier octet.

    '192.168.1.42' -> ('192.168.1.', '42')

    Le dernier octet seul est conservé côté DB. Permet de détecter des
    consentements répétés depuis la même machine sans violer la minimisation
    RGPD (on ne peut pas remonter à la personne).
    """
    if not ip:
        return "", ""
    if ":" in ip:
        # IPv6 : on garde les 3 derniers caractères du groupe final
        groups = ip.split(":")
        last = groups[-1] if groups else ""
        return "", last[-3:] if last else ""
    parts = ip.split(".")
    if len(parts) != 4:
        return "", ""
    return ".".join(parts[:3]) + ".", parts[3][:3]


def _get_client_ip(request) -> str:
    """
    Récupère l'IP du client en tenant compte des proxies (X-Forwarded-For).

    Sur Railway / Heroku / Cloudflare, la vraie IP client est dans
    X-Forwarded-For, pas dans REMOTE_ADDR (qui contient l'IP du proxy).
    """
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        # Format : "client_ip, proxy1_ip, proxy2_ip"
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def _session_hash(request) -> str:
    """
    Génère un hash stable pour identifier une session anonyme sans stocker
    de donnée personnelle.

    Composants : IP + user-agent -> SHA-256.
    Propriété : ne permet pas de remonter à l'IP d'origine (hash à sens unique),
    mais permet de détecter le même visiteur sur plusieurs consentements.
    """
    ip = _get_client_ip(request)
    ua = request.META.get("HTTP_USER_AGENT", "")
    raw = f"{ip}|{ua}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def record_masking_consent(request, endpoint: str, consent_text: str = "") -> bool:
    """
    Enregistre un consentement explicite de désactivation du masquage RGPD.

    Args:
        request      : objet request Django (pour extraire user, IP, UA)
        endpoint     : URL de l'endpoint concerné, ex: '/api/procedures/ingest/'
        consent_text : texte exact que l'utilisateur a accepté.
                       Si vide ou invalide, on utilise DEFAULT_CONSENT_TEXT.

    Returns:
        True si le consentement a été enregistré, False en cas d'échec
        (ex: table inexistante, erreur DB). L'échec n'est PAS fatal pour
        la requête : il est juste loggé en warning.
    """
    try:
        from procedures.models import MaskingConsent
    except ImportError:
        logger.error("Modèle MaskingConsent introuvable : migration appliquée ?")
        return False

    # Validation / nettoyage du texte de consentement
    text_to_record = (consent_text or "").strip()
    if not text_to_record:
        text_to_record = DEFAULT_CONSENT_TEXT
    elif not all(kw in text_to_record for kw in REQUIRED_CONSENT_KEYWORDS):
        # Le frontend n'a pas affiché le bon texte de consentement. Suspect.
        # On garde une trace de la tentative mais on utilise le texte par défaut.
        logger.warning(
            f"Consentement reçu sans mots-clés obligatoires "
            f"{REQUIRED_CONSENT_KEYWORDS}. Fallback sur DEFAULT_CONSENT_TEXT."
        )
        text_to_record = DEFAULT_CONSENT_TEXT

    # Contexte de la requête
    user = request.user if hasattr(request, "user") and request.user.is_authenticated else None
    ua = request.META.get("HTTP_USER_AGENT", "")[:255]
    ip = _get_client_ip(request)
    _, last_octet = _anonymize_ip(ip)

    try:
        MaskingConsent.objects.create(
            user=user,
            # Hash de session uniquement pour les anonymes
            session_hash=_session_hash(request) if user is None else "",
            endpoint=endpoint[:100],
            consent_text=text_to_record,
            user_agent=ua,
            ip_last_octet=last_octet,
        )
        return True
    except Exception as e:
        logger.error(f"Échec de l'enregistrement du consentement : {e}")
        return False
