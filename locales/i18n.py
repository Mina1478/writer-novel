"""
i18n (Internationalization) module for AI Novel Generator.
Loads locale-specific JSON files and provides a simple t(key) function to retrieve translated strings.

Usage:
    from locales.i18n import t, set_language

    set_language("VI")  # Switch to Vietnamese
    print(t("app.title"))  # Prints Vietnamese title

Language can also be set via environment variable APP_LANGUAGE (default: "VI").
"""

import json
import os
import logging

logger = logging.getLogger("i18n")

# Global state
_current_language = None
_translations = {}
_locales_dir = os.path.dirname(os.path.abspath(__file__))


def load_locale(lang: str) -> dict:
    """Load a locale JSON file and return the translations dict."""
    locale_path = os.path.join(_locales_dir, lang, "messages.json")
    if not os.path.exists(locale_path):
        logger.error(f"Locale file not found: {locale_path}")
        return {}

    try:
        with open(locale_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Failed to load locale '{lang}': {e}")
        return {}


def set_language(lang: str) -> None:
    """Set the active language and load its translations."""
    global _current_language, _translations
    _current_language = lang
    _translations = load_locale(lang)
    if _translations:
        logger.info(f"Language set to: {lang}")
    else:
        logger.warning(f"No translations loaded for language: {lang}")


def get_language() -> str:
    """Return the current language code."""
    return _current_language or "VI"


def t(key: str, **kwargs) -> str:
    """
    Translate a dot-notation key to the localized string.

    Args:
        key: Dot-separated key path, e.g. "tabs.rewrite" or "messages.polish_success"
        **kwargs: Optional format parameters to interpolate into the string.

    Returns:
        The translated string, or the key itself if not found (for debugging).
    """
    global _translations

    # Auto-initialize if not yet loaded
    if not _translations:
        init_lang = os.getenv("APP_LANGUAGE", "VI")
        set_language(init_lang)

    # Traverse the nested dict
    parts = key.split(".")
    value = _translations
    for part in parts:
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            logger.warning(f"Missing translation key: '{key}' (language: {_current_language})")
            return key  # Return the key itself as fallback

    if isinstance(value, str):
        if kwargs:
            try:
                return value.format(**kwargs)
            except KeyError:
                return value
        return value

    # If value is a list (e.g. dropdown choices), return it directly
    if isinstance(value, list):
        return value

    # If value is still a dict, return the key
    logger.warning(f"Translation key '{key}' resolved to a dict, not a string")
    return key


# Auto-initialize on import
_init_lang = os.getenv("APP_LANGUAGE", "VI")
set_language(_init_lang)
