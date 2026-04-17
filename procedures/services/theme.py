import json
import os
from pathlib import Path
from reportlab.lib import colors

# Chemin vers le thème par défaut
DEFAULT_THEME_PATH = Path(__file__).resolve().parent.parent / 'themes' / 'default.json'


def load_default_theme() -> dict:
    """Charge le thème par défaut depuis le fichier JSON."""
    with open(DEFAULT_THEME_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def merge_themes(default: dict, override: dict) -> dict:
    """
    Fusionne le thème par défaut avec les préférences de l'organisation.
    Les clés de l'override remplacent celles du défaut — récursivement.
    """
    result = default.copy()
    for key, value in override.items():
        if isinstance(value, dict) and key in result and isinstance(result[key], dict):
            result[key] = merge_themes(result[key], value)
        else:
            result[key] = value
    return result


def get_theme(organization=None) -> dict:
    """
    Retourne le thème final pour une organisation.
    Si l'organisation a un thème personnalisé, il est fusionné avec le défaut.
    """
    default = load_default_theme()

    if organization and organization.theme:
        return merge_themes(default, organization.theme)

    return default


def hex_to_color(hex_str: str):
    """Convertit une couleur hex (#RRGGBB) en objet couleur ReportLab."""
    return colors.HexColor(hex_str)


class ThemeColors:
    """
    Classe utilitaire pour accéder aux couleurs du thème
    sous forme d'objets ReportLab directement.
    """
    def __init__(self, theme: dict):
        c = theme.get('colors', {})
        self.primary    = hex_to_color(c.get('primary',    '#1B3A5C'))
        self.secondary  = hex_to_color(c.get('secondary',  '#2E6DA4'))
        self.light      = hex_to_color(c.get('light',      '#D6E4F0'))
        self.background = hex_to_color(c.get('background', '#F5F7FA'))
        self.text       = hex_to_color(c.get('text',       '#4A4A4A'))
        self.success    = hex_to_color(c.get('success',    '#1E7A4A'))
        self.warning    = hex_to_color(c.get('warning',    '#C76B00'))
        self.danger     = hex_to_color(c.get('danger',     '#CC0000'))
        self.white      = hex_to_color(c.get('white',      '#FFFFFF'))