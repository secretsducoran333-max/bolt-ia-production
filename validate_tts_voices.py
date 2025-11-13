"""
Script para validar e listar todas as vozes disponíveis no Google Cloud TTS.
"""
import json
from collections import defaultdict

# Simulação das vozes disponíveis (baseado na documentação oficial do Google Cloud TTS)
# Em produção, isso seria obtido via: client = texttospeech.TextToSpeechClient(); voices = client.list_voices()

GOOGLE_TTS_VOICES = {
    # Português
    "pt-BR": ["pt-BR-Neural2-A", "pt-BR-Neural2-B", "pt-BR-Neural2-C", "pt-BR-Wavenet-A", "pt-BR-Wavenet-B", "pt-BR-Standard-A"],
    "pt-PT": ["pt-PT-Wavenet-A", "pt-PT-Wavenet-B", "pt-PT-Wavenet-C", "pt-PT-Wavenet-D"],
    
    # Inglês
    "en-US": ["en-US-Neural2-A", "en-US-Neural2-C", "en-US-Neural2-D", "en-US-Neural2-E", "en-US-Neural2-F", 
              "en-US-Neural2-G", "en-US-Neural2-H", "en-US-Neural2-I", "en-US-Neural2-J",
              "en-US-Wavenet-A", "en-US-Wavenet-B", "en-US-Wavenet-C", "en-US-Wavenet-D"],
    "en-GB": ["en-GB-Neural2-A", "en-GB-Neural2-B", "en-GB-Neural2-C", "en-GB-Neural2-D", "en-GB-Neural2-F",
              "en-GB-Wavenet-A", "en-GB-Wavenet-B", "en-GB-Wavenet-C", "en-GB-Wavenet-D"],
    "en-AU": ["en-AU-Neural2-A", "en-AU-Neural2-B", "en-AU-Neural2-C", "en-AU-Neural2-D",
              "en-AU-Wavenet-A", "en-AU-Wavenet-B", "en-AU-Wavenet-C", "en-AU-Wavenet-D"],
    "en-IN": ["en-IN-Neural2-A", "en-IN-Neural2-B", "en-IN-Neural2-C", "en-IN-Neural2-D",
              "en-IN-Wavenet-A", "en-IN-Wavenet-B", "en-IN-Wavenet-C", "en-IN-Wavenet-D"],
    
    # Espanhol
    "es-ES": ["es-ES-Neural2-A", "es-ES-Neural2-B", "es-ES-Neural2-C", "es-ES-Neural2-D", "es-ES-Neural2-E", "es-ES-Neural2-F",
              "es-ES-Wavenet-B", "es-ES-Wavenet-C", "es-ES-Wavenet-D"],
    "es-US": ["es-US-Neural2-A", "es-US-Neural2-B", "es-US-Neural2-C",
              "es-US-Wavenet-A", "es-US-Wavenet-B", "es-US-Wavenet-C"],
    
    # Francês
    "fr-FR": ["fr-FR-Neural2-A", "fr-FR-Neural2-B", "fr-FR-Neural2-C", "fr-FR-Neural2-D", "fr-FR-Neural2-E",
              "fr-FR-Wavenet-A", "fr-FR-Wavenet-B", "fr-FR-Wavenet-C", "fr-FR-Wavenet-D"],
    "fr-CA": ["fr-CA-Neural2-A", "fr-CA-Neural2-B", "fr-CA-Neural2-C", "fr-CA-Neural2-D",
              "fr-CA-Wavenet-A", "fr-CA-Wavenet-B", "fr-CA-Wavenet-C", "fr-CA-Wavenet-D"],
    
    # Alemão
    "de-DE": ["de-DE-Neural2-A", "de-DE-Neural2-B", "de-DE-Neural2-C", "de-DE-Neural2-D", "de-DE-Neural2-F",
              "de-DE-Wavenet-A", "de-DE-Wavenet-B", "de-DE-Wavenet-C", "de-DE-Wavenet-D"],
    
    # Italiano
    "it-IT": ["it-IT-Neural2-A", "it-IT-Neural2-C",
              "it-IT-Wavenet-A", "it-IT-Wavenet-B", "it-IT-Wavenet-C", "it-IT-Wavenet-D"],
    
    # Japonês
    "ja-JP": ["ja-JP-Neural2-B", "ja-JP-Neural2-C", "ja-JP-Neural2-D",
              "ja-JP-Wavenet-A", "ja-JP-Wavenet-B", "ja-JP-Wavenet-C", "ja-JP-Wavenet-D"],
    
    # Coreano
    "ko-KR": ["ko-KR-Neural2-A", "ko-KR-Neural2-B", "ko-KR-Neural2-C",
              "ko-KR-Wavenet-A", "ko-KR-Wavenet-B", "ko-KR-Wavenet-C", "ko-KR-Wavenet-D"],
    
    # Chinês
    "cmn-CN": ["cmn-CN-Wavenet-A", "cmn-CN-Wavenet-B", "cmn-CN-Wavenet-C", "cmn-CN-Wavenet-D"],
    "cmn-TW": ["cmn-TW-Wavenet-A", "cmn-TW-Wavenet-B", "cmn-TW-Wavenet-C"],
    
    # Hindi
    "hi-IN": ["hi-IN-Neural2-A", "hi-IN-Neural2-B", "hi-IN-Neural2-C", "hi-IN-Neural2-D",
              "hi-IN-Wavenet-A", "hi-IN-Wavenet-B", "hi-IN-Wavenet-C", "hi-IN-Wavenet-D"],
    
    # Árabe
    "ar-XA": ["ar-XA-Wavenet-A", "ar-XA-Wavenet-B", "ar-XA-Wavenet-C"],
    
    # Russo
    "ru-RU": ["ru-RU-Wavenet-A", "ru-RU-Wavenet-B", "ru-RU-Wavenet-C", "ru-RU-Wavenet-D", "ru-RU-Wavenet-E"],
    
    # Polonês
    "pl-PL": ["pl-PL-Wavenet-A", "pl-PL-Wavenet-B", "pl-PL-Wavenet-C", "pl-PL-Wavenet-D", "pl-PL-Wavenet-E"],
    
    # Turco
    "tr-TR": ["tr-TR-Wavenet-A", "tr-TR-Wavenet-B", "tr-TR-Wavenet-C", "tr-TR-Wavenet-D", "tr-TR-Wavenet-E"],
    
    # Holandês
    "nl-NL": ["nl-NL-Wavenet-A", "nl-NL-Wavenet-B", "nl-NL-Wavenet-C", "nl-NL-Wavenet-D", "nl-NL-Wavenet-E"],
    
    # Sueco
    "sv-SE": ["sv-SE-Wavenet-A", "sv-SE-Wavenet-B", "sv-SE-Wavenet-C"],
    
    # Norueguês
    "nb-NO": ["nb-NO-Wavenet-A", "nb-NO-Wavenet-B", "nb-NO-Wavenet-C", "nb-NO-Wavenet-D", "nb-NO-Wavenet-E"],
    
    # Dinamarquês
    "da-DK": ["da-DK-Wavenet-A", "da-DK-Wavenet-C", "da-DK-Wavenet-D", "da-DK-Wavenet-E"],
    
    # Finlandês
    "fi-FI": ["fi-FI-Wavenet-A"],
    
    # Grego
    "el-GR": ["el-GR-Wavenet-A"],
    
    # Tcheco
    "cs-CZ": ["cs-CZ-Wavenet-A"],
    
    # Húngaro
    "hu-HU": ["hu-HU-Wavenet-A"],
    
    # Indonésio
    "id-ID": ["id-ID-Wavenet-A", "id-ID-Wavenet-B", "id-ID-Wavenet-C", "id-ID-Wavenet-D"],
    
    # Tailandês
    "th-TH": ["th-TH-Neural2-C"],
    
    # Vietnamita
    "vi-VN": ["vi-VN-Neural2-A", "vi-VN-Neural2-D", "vi-VN-Wavenet-A", "vi-VN-Wavenet-B", "vi-VN-Wavenet-C", "vi-VN-Wavenet-D"],
    
    # Filipino
    "fil-PH": ["fil-PH-Wavenet-A", "fil-PH-Wavenet-B", "fil-PH-Wavenet-C", "fil-PH-Wavenet-D"],
    
    # Ucraniano
    "uk-UA": ["uk-UA-Wavenet-A"],
    
    # Eslovaco
    "sk-SK": ["sk-SK-Wavenet-A"],
}

def generate_voice_catalog():
    """Gera catálogo completo de vozes."""
    total_voices = sum(len(voices) for voices in GOOGLE_TTS_VOICES.values())
    
    print(f"📊 Total de idiomas suportados: {len(GOOGLE_TTS_VOICES)}")
    print(f"📊 Total de vozes disponíveis: {total_voices}")
    print(f"📊 Média de vozes por idioma: {total_voices / len(GOOGLE_TTS_VOICES):.1f}")
    print()
    
    # Salvar em JSON
    with open('tts_voices_catalog.json', 'w', encoding='utf-8') as f:
        json.dump(GOOGLE_TTS_VOICES, f, indent=2, ensure_ascii=False)
    
    print("✅ Catálogo salvo em: tts_voices_catalog.json")
    
    # Estatísticas por idioma
    print("\n📋 Vozes por idioma:")
    for lang, voices in sorted(GOOGLE_TTS_VOICES.items()):
        print(f"  {lang}: {len(voices)} vozes")
    
    return GOOGLE_TTS_VOICES

if __name__ == "__main__":
    generate_voice_catalog()
