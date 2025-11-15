# 🚀 Guia Rápido - BoredFy AI

## ⚡ Início Rápido (5 minutos)

### 1️⃣ Instalar e Rodar

```bash
# Clone o repositório
git clone https://github.com/secretsducoran333-max/bolt-ia-production.git
cd bolt-ia-production

# Crie ambiente virtual
python3.11 -m venv venv
source venv/bin/activate

# Instale dependências
pip install fastapi uvicorn sqlalchemy python-jose python-multipart \
    google-generativeai google-cloud-texttospeech langdetect \
    pydantic pydantic-settings python-dotenv argon2-cffi email-validator

# Configure .env
cp .env.example .env
# Edite .env e altere SECRET_KEY

# Inicie o servidor
python main.py
```

Acesse: **http://localhost:8000**

---

### 2️⃣ Primeiro Uso

1. **Criar conta**
   - Email: seu@email.com
   - Senha: mínimo 6 caracteres

2. **Adicionar API Key do Gemini**
   - Obtenha em: https://makersuite.google.com/app/apikey
   - Cole no campo "API Key"
   - Clique em "Adicionar"

3. **Criar seu primeiro agente**
   - Nome: "Meu Agente de Teste"
   - Idioma: pt-BR
   - Preencha os templates básicos
   - Salvar

4. **Gerar roteiro**
   - Selecione o agente
   - Digite um título: "História sobre um robô"
   - Clique em "Gerar"
   - Aguarde o progresso

5. **Baixar resultado**
   - Vá em "Meus Arquivos"
   - Baixe o roteiro gerado

---

## 🎯 Casos de Uso Comuns

### Gerar roteiros em múltiplos idiomas

```
1. Crie um agente
2. Idioma principal: pt-BR
3. Idiomas adicionais: ["en-US", "es-ES"]
4. Preencha template de adaptação cultural
5. Gere roteiro → receberá 3 versões
```

### Gerar roteiros com áudio (TTS)

```
1. Crie/edite um agente
2. Ative "TTS Enabled"
3. Selecione vozes para cada idioma:
   - pt-BR: "Maria - Português Brasileiro (Feminino)"
   - en-US: "Emma - American English (Female)"
4. Gere roteiro → receberá roteiro + áudio
```

### Criar agente a partir de roteiros existentes

```
1. Clique em "Criar Agente com IA"
2. Digite nome do agente
3. Faça upload de 2-6 roteiros exemplo (.txt)
4. A IA analisará e criará templates automaticamente
5. Revise e salve
```

---

## 📊 Entendendo o Dashboard

### Stats Principais

- **Roteiros Hoje**: Quantos roteiros você gerou hoje
- **TTS Hoje**: Quantos áudios gerou hoje
- **Nível**: Seu nível atual (baseado em XP)
- **XP**: Experiência acumulada
  - 10 XP por roteiro gerado
  - 5 XP por áudio gerado
- **Streak**: Dias consecutivos usando a plataforma

### Fila de Jobs

- **Pending**: Aguardando processamento
- **Processing**: Em andamento (veja progresso 0-100%)
- **Completed**: Concluído (arquivos disponíveis)
- **Failed**: Falhou (veja log de erro)
- **Cancelled**: Cancelado por você

---

## 🔧 Troubleshooting

### Erro: "API key inválida"

✅ Verifique se a chave do Gemini está correta
✅ Teste em: https://makersuite.google.com/app/apikey

### Erro: "Sessão expirada"

✅ Faça login novamente
✅ Token expira após 24h (padrão)

### Job fica em "Processing" indefinidamente

✅ Verifique o log do job
✅ Pode ser timeout da API do Gemini
✅ Tente novamente com texto menor

### Áudio não é gerado

✅ Verifique se TTS está ativado no agente
✅ Verifique se selecionou voz para o idioma
✅ Google Cloud TTS requer configuração adicional

---

## 💡 Dicas e Truques

### Otimize seus prompts

**Ruim:**
```
Crie um roteiro
```

**Bom:**
```
Template de Premissa:
Você é um roteirista especializado em [NICHO].
Crie premissas criativas e envolventes sobre [TEMA].

Template de Roteiro:
- Introdução: Apresente o contexto em 2-3 frases
- Desenvolvimento: Desenvolva a história em 3-4 parágrafos
- Conclusão: Finalize com reflexão ou call-to-action
- Tom: [Informal/Formal/Educativo/Humorístico]
- Público-alvo: [Definir]
```

### Use blocos estruturados

```
Bloco 1: Hook (10% do roteiro)
- Capturar atenção nos primeiros 5 segundos

Bloco 2: Contexto (20% do roteiro)
- Apresentar problema/situação

Bloco 3: Desenvolvimento (50% do roteiro)
- Explorar solução/história principal

Bloco 4: Conclusão (20% do roteiro)
- Resumir e call-to-action
```

### Adaptação cultural efetiva

```
Ao adaptar para [IDIOMA]:
1. Substitua expressões idiomáticas por equivalentes locais
2. Adapte referências culturais (ex: futebol → baseball para en-US)
3. Ajuste unidades de medida (km → miles para en-US)
4. Mantenha o tom e intenção original
5. Adapte exemplos para contexto local
```

---

## 🎨 Personalização Avançada

### Alterar tempo de expiração do token

Edite `.env`:
```env
ACCESS_TOKEN_EXPIRE_MINUTES=2880  # 48 horas
```

### Usar PostgreSQL em produção

Edite `.env`:
```env
DATABASE_URL=postgresql://user:password@localhost/boredfy_ai
```

Instale driver:
```bash
pip install psycopg2-binary
```

### Deploy com Gunicorn

```bash
pip install gunicorn
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

---

## 📞 Precisa de Ajuda?

- 📖 Leia o README.md completo
- 🐛 Abra uma issue no GitHub
- 💬 Entre em contato com o suporte

---

**Bom uso! 🚀**
