# voices_config.py - Configuração de 30 vozes premium para TTS

PREMIUM_VOICES = [
    # Português Brasileiro (5 vozes)
    {"voice_id": "pt-BR-Neural2-A", "name": "Maria - Português Brasileiro (Feminino)", "language_code": "pt-BR", "gender": "female", "service": "GoogleTTS"},
    {"voice_id": "pt-BR-Neural2-B", "name": "João - Português Brasileiro (Masculino)", "language_code": "pt-BR", "gender": "male", "service": "GoogleTTS"},
    {"voice_id": "pt-BR-Neural2-C", "name": "Ana - Português Brasileiro (Feminino)", "language_code": "pt-BR", "gender": "female", "service": "GoogleTTS"},
    {"voice_id": "pt-BR-Wavenet-A", "name": "Carla - Português Brasileiro (Feminino)", "language_code": "pt-BR", "gender": "female", "service": "GoogleTTS"},
    {"voice_id": "pt-BR-Wavenet-B", "name": "Pedro - Português Brasileiro (Masculino)", "language_code": "pt-BR", "gender": "male", "service": "GoogleTTS"},
    
    # Inglês Americano (5 vozes)
    {"voice_id": "en-US-Neural2-A", "name": "Emma - American English (Female)", "language_code": "en-US", "gender": "female", "service": "GoogleTTS"},
    {"voice_id": "en-US-Neural2-D", "name": "James - American English (Male)", "language_code": "en-US", "gender": "male", "service": "GoogleTTS"},
    {"voice_id": "en-US-Neural2-F", "name": "Sophia - American English (Female)", "language_code": "en-US", "gender": "female", "service": "GoogleTTS"},
    {"voice_id": "en-US-Wavenet-A", "name": "Olivia - American English (Female)", "language_code": "en-US", "gender": "female", "service": "GoogleTTS"},
    {"voice_id": "en-US-Wavenet-D", "name": "Michael - American English (Male)", "language_code": "en-US", "gender": "male", "service": "GoogleTTS"},
    
    # Espanhol (5 vozes)
    {"voice_id": "es-ES-Neural2-A", "name": "Lucía - Español (Femenino)", "language_code": "es-ES", "gender": "female", "service": "GoogleTTS"},
    {"voice_id": "es-ES-Neural2-B", "name": "Carlos - Español (Masculino)", "language_code": "es-ES", "gender": "male", "service": "GoogleTTS"},
    {"voice_id": "es-US-Neural2-A", "name": "Isabella - Español Americano (Femenino)", "language_code": "es-US", "gender": "female", "service": "GoogleTTS"},
    {"voice_id": "es-US-Neural2-B", "name": "Diego - Español Americano (Masculino)", "language_code": "es-US", "gender": "male", "service": "GoogleTTS"},
    {"voice_id": "es-MX-Wavenet-A", "name": "Sofía - Español Mexicano (Femenino)", "language_code": "es-MX", "gender": "female", "service": "GoogleTTS"},
    
    # Francês (3 vozes)
    {"voice_id": "fr-FR-Neural2-A", "name": "Amélie - Français (Féminin)", "language_code": "fr-FR", "gender": "female", "service": "GoogleTTS"},
    {"voice_id": "fr-FR-Neural2-B", "name": "Pierre - Français (Masculin)", "language_code": "fr-FR", "gender": "male", "service": "GoogleTTS"},
    {"voice_id": "fr-FR-Wavenet-A", "name": "Chloé - Français (Féminin)", "language_code": "fr-FR", "gender": "female", "service": "GoogleTTS"},
    
    # Alemão (3 vozes)
    {"voice_id": "de-DE-Neural2-A", "name": "Hannah - Deutsch (Weiblich)", "language_code": "de-DE", "gender": "female", "service": "GoogleTTS"},
    {"voice_id": "de-DE-Neural2-B", "name": "Lukas - Deutsch (Männlich)", "language_code": "de-DE", "gender": "male", "service": "GoogleTTS"},
    {"voice_id": "de-DE-Wavenet-A", "name": "Emma - Deutsch (Weiblich)", "language_code": "de-DE", "gender": "female", "service": "GoogleTTS"},
    
    # Italiano (2 vozes)
    {"voice_id": "it-IT-Neural2-A", "name": "Giulia - Italiano (Femminile)", "language_code": "it-IT", "gender": "female", "service": "GoogleTTS"},
    {"voice_id": "it-IT-Neural2-C", "name": "Marco - Italiano (Maschile)", "language_code": "it-IT", "gender": "male", "service": "GoogleTTS"},
    
    # Japonês (2 vozes)
    {"voice_id": "ja-JP-Neural2-B", "name": "Sakura - 日本語 (女性)", "language_code": "ja-JP", "gender": "female", "service": "GoogleTTS"},
    {"voice_id": "ja-JP-Neural2-C", "name": "Takeshi - 日本語 (男性)", "language_code": "ja-JP", "gender": "male", "service": "GoogleTTS"},
    
    # Coreano (2 vozes)
    {"voice_id": "ko-KR-Neural2-A", "name": "Ji-woo - 한국어 (여성)", "language_code": "ko-KR", "gender": "female", "service": "GoogleTTS"},
    {"voice_id": "ko-KR-Neural2-C", "name": "Min-jun - 한국어 (남성)", "language_code": "ko-KR", "gender": "male", "service": "GoogleTTS"},
    
    # Chinês Mandarim (2 vozes)
    {"voice_id": "cmn-CN-Wavenet-A", "name": "Xiaomei - 中文 (女性)", "language_code": "cmn-CN", "gender": "female", "service": "GoogleTTS"},
    {"voice_id": "cmn-CN-Wavenet-B", "name": "Xiaoyu - 中文 (男性)", "language_code": "cmn-CN", "gender": "male", "service": "GoogleTTS"},
    
    # Árabe (1 voz)
    {"voice_id": "ar-XA-Wavenet-A", "name": "Fatima - العربية (أنثى)", "language_code": "ar-XA", "gender": "female", "service": "GoogleTTS"},
]

# Mapeamento de idiomas suportados (100+ idiomas via detecção automática)
SUPPORTED_LANGUAGES = {
    "pt-BR": "Português Brasileiro",
    "pt-PT": "Português Europeu",
    "en-US": "English (US)",
    "en-GB": "English (UK)",
    "es-ES": "Español",
    "es-MX": "Español Mexicano",
    "es-US": "Español Americano",
    "fr-FR": "Français",
    "de-DE": "Deutsch",
    "it-IT": "Italiano",
    "ja-JP": "日本語",
    "ko-KR": "한국어",
    "cmn-CN": "中文",
    "ar-XA": "العربية",
    "ru-RU": "Русский",
    "hi-IN": "हिन्दी",
    "nl-NL": "Nederlands",
    "pl-PL": "Polski",
    "tr-TR": "Türkçe",
    "vi-VN": "Tiếng Việt",
    # ... (mais idiomas podem ser adicionados conforme necessário)
}

def get_voices_by_language(language_code: str):
    """Retorna vozes disponíveis para um idioma específico"""
    return [v for v in PREMIUM_VOICES if v["language_code"] == language_code]

def get_all_voices():
    """Retorna todas as vozes premium"""
    return PREMIUM_VOICES

def get_voice_by_id(voice_id: str):
    """Retorna uma voz específica pelo ID"""
    for voice in PREMIUM_VOICES:
        if voice["voice_id"] == voice_id:
            return voice
    return None
