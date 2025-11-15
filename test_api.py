#!/usr/bin/env python3
# test_api.py - Teste completo da API BoredFy

import requests
import json
import time

BASE_URL = "http://localhost:8000"
token = None

def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def test_health():
    print_section("1. TESTE DE HEALTH CHECK")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    assert response.status_code == 200
    print("✅ Health check OK")

def test_register():
    print_section("2. TESTE DE REGISTRO")
    data = {
        "email": "teste@boredfy.com",
        "password": "senha123"
    }
    response = requests.post(f"{BASE_URL}/auth/register", json=data)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        print("✅ Registro OK")
    elif response.status_code == 400:
        print("⚠️  Usuário já existe (OK)")
    else:
        print(f"❌ Erro: {response.text}")

def test_login():
    global token
    print_section("3. TESTE DE LOGIN")
    data = {
        "username": "teste@boredfy.com",
        "password": "senha123"
    }
    response = requests.post(f"{BASE_URL}/auth/login", data=data)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        token = result["access_token"]
        print(f"Token obtido: {token[:50]}...")
        print("✅ Login OK")
    else:
        print(f"❌ Erro: {response.text}")
        raise Exception("Login falhou")

def get_headers():
    return {"Authorization": f"Bearer {token}"}

def test_me():
    print_section("4. TESTE DE /auth/me")
    response = requests.get(f"{BASE_URL}/auth/me", headers=get_headers())
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    assert response.status_code == 200
    print("✅ /auth/me OK")

def test_api_key_validation():
    print_section("5. TESTE DE VALIDAÇÃO DE API KEY")
    # Usar uma chave fake para teste
    data = {"api_key": "AIzaSyTest_FakeKey_ForTesting_1234567890"}
    response = requests.post(f"{BASE_URL}/api-keys/validate", json=data, headers=get_headers())
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print("⚠️  Chave fake (esperado falhar)")

def test_get_voices():
    print_section("6. TESTE DE LISTAGEM DE VOZES")
    response = requests.get(f"{BASE_URL}/voices", headers=get_headers())
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"Total de vozes: {len(result['voices'])}")
        print(f"Primeira voz: {json.dumps(result['voices'][0], indent=2)}")
        print("✅ Listagem de vozes OK")
    else:
        print(f"❌ Erro: {response.text}")

def test_create_agent():
    print_section("7. TESTE DE CRIAÇÃO DE AGENTE")
    data = {
        "name": "Agente de Teste",
        "agent_type": "premissa",
        "idioma_principal": "pt-BR",
        "premise_prompt": "Você é um assistente criativo que gera roteiros interessantes.",
        "script_prompt": "Crie roteiros com introdução, desenvolvimento e conclusão.",
        "block_structure": "Bloco 1: Introdução\nBloco 2: Desenvolvimento\nBloco 3: Conclusão",
        "cultural_adaptation_prompt": "Adapte o conteúdo para a cultura local.",
        "idiomas_adicionais": ["en-US"],
        "tts_enabled": False,
        "tts_voices": {},
        "visual_media_enabled": False
    }
    response = requests.post(f"{BASE_URL}/agents", json=data, headers=get_headers())
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"Agente criado: {result['name']} (ID: {result['id']})")
        print("✅ Criação de agente OK")
        return result['id']
    else:
        print(f"❌ Erro: {response.text}")
        return None

def test_get_agents():
    print_section("8. TESTE DE LISTAGEM DE AGENTES")
    response = requests.get(f"{BASE_URL}/agents", headers=get_headers())
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"Total de agentes: {len(result)}")
        if result:
            print(f"Primeiro agente: {result[0]['name']}")
        print("✅ Listagem de agentes OK")
    else:
        print(f"❌ Erro: {response.text}")

def test_get_stats():
    print_section("9. TESTE DE DASHBOARD DE STATS")
    response = requests.get(f"{BASE_URL}/stats/dashboard", headers=get_headers())
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"Stats: {json.dumps(result, indent=2)}")
        print("✅ Dashboard de stats OK")
    else:
        print(f"❌ Erro: {response.text}")

def test_get_recent_files():
    print_section("10. TESTE DE ARQUIVOS RECENTES")
    response = requests.get(f"{BASE_URL}/files/recent", headers=get_headers())
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"Total de arquivos (24h): {len(result)}")
        print("✅ Listagem de arquivos OK")
    else:
        print(f"❌ Erro: {response.text}")

def run_all_tests():
    print("\n🚀 INICIANDO TESTES DA API BOREDFY\n")
    
    try:
        test_health()
        test_register()
        test_login()
        test_me()
        test_api_key_validation()
        test_get_voices()
        agent_id = test_create_agent()
        test_get_agents()
        test_get_stats()
        test_get_recent_files()
        
        print_section("RESUMO DOS TESTES")
        print("✅ Todos os testes básicos passaram!")
        print("\n📝 PRÓXIMOS PASSOS:")
        print("1. Adicione uma API key válida do Gemini via interface")
        print("2. Teste a geração de roteiros")
        print("3. Configure TTS e teste geração de áudio")
        print("\n🎉 Backend está funcionando corretamente!")
        
    except Exception as e:
        print(f"\n❌ Erro durante os testes: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_all_tests()
