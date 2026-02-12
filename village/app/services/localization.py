# app/services/localization.py
from app.bot.texts_ru import TEXTS as TEXTS_RU

class Localization:
    TRANSLATIONS = {
        'ru': TEXTS_RU,
    }
    
    @staticmethod
    def get(lang: str, key: str, **kwargs) -> str:
        """Get localized text"""
        translations = Localization.TRANSLATIONS.get(lang, Localization.TRANSLATIONS['ru'])
        text = translations.get(key, f'[{key}]')
        
        if kwargs:
            try:
                return text.format(**kwargs)
            except KeyError:
                return text
        return text