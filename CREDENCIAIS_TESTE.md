# 🔐 Credenciais de Teste

## Usuário de Teste Criado

**Email:** teste@boredfy.com  
**Senha:** senha123

---

## Como Testar

1. Acesse: https://8000-i33l4hj551zrzx563uz4j-a7701cd5.manusvm.computer
2. Faça login com as credenciais acima
3. Adicione sua API key do Gemini
4. Crie um agente e teste a geração!

---

## Obter API Key do Gemini (Gratuita)

1. Acesse: https://makersuite.google.com/app/apikey
2. Clique em "Create API Key"
3. Copie a chave gerada
4. Cole no dashboard do BoredFy

---

## Endpoints da API

**Base URL:** https://8000-i33l4hj551zrzx563uz4j-a7701cd5.manusvm.computer

### Testar Health Check

```bash
curl https://8000-i33l4hj551zrzx563uz4j-a7701cd5.manusvm.computer/health
```

### Fazer Login via API

```bash
curl -X POST https://8000-i33l4hj551zrzx563uz4j-a7701cd5.manusvm.computer/auth/login \
  -F "username=teste@boredfy.com" \
  -F "password=senha123"
```

---

## Notas

- O servidor está rodando em modo de desenvolvimento
- O banco de dados é SQLite (local)
- Arquivos gerados ficam disponíveis por 24 horas
- Para produção, configure PostgreSQL e variáveis de ambiente adequadas

---

**Divirta-se testando! 🎉**
