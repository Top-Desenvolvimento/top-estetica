# 🦷 Top Estética Bucal — PIX Doutores Automático

## Como funciona

```
GitHub Actions (nuvem gratuita)
    ↓  roda a cada hora automaticamente
scraper.py
    ↓  faz login em cada cidade e captura os dados
dados.json  ←  salvo no próprio repositório
    ↓  dashboard lê direto do GitHub
dashboard.html  →  você abre no navegador, sem custo algum
```

---

## ✅ PASSO A PASSO — Configure em 15 minutos

### 1. Criar conta no GitHub (gratuito)
- Acesse https://github.com e clique em **Sign up**
- Crie uma conta com seu e-mail

### 2. Criar o repositório
- Clique em **New repository** (botão verde)
- Nome: `top-estetica`
- Marque **Private** (seus dados ficam privados)
- Clique em **Create repository**

### 3. Fazer upload dos arquivos
- Na página do repositório, clique em **uploading an existing file**
- Faça upload de todos os arquivos desta pasta:
  - `dashboard.html`
  - `requirements.txt`
  - `scripts/scraper.py`
  - `.github/workflows/scraper.yml`
- Clique em **Commit changes**

### 4. Configurar as credenciais (segredos)
- No repositório, clique em **Settings** → **Secrets and variables** → **Actions**
- Clique em **New repository secret** e adicione:
  - Nome: `SISTEMA_USER`  |  Valor: `MANUS`
  - Nome: `SISTEMA_PASS`  |  Valor: `MANUS2026`

### 5. Rodar pela primeira vez
- Vá em **Actions** → clique no workflow **"Atualizar PIX Doutores"**
- Clique em **Run workflow** → **Run workflow**
- Aguarde ~5 minutos para concluir
- Verifique se o arquivo `scripts/dados.json` foi criado

### 6. Obter a URL do dados.json
- Abra o arquivo `scripts/dados.json` no repositório
- Clique em **Raw**
- Copie a URL da barra de endereços
  (será algo como: `https://raw.githubusercontent.com/SEU-USUARIO/top-estetica/main/scripts/dados.json`)

### 7. Abrir a dashboard
- Abra o arquivo `dashboard.html` no navegador (duplo clique)
- No campo **"URL do arquivo dados.json"**, cole a URL copiada acima
- Pronto! A dashboard vai carregar os dados automaticamente

---

## 📅 Atualização automática

O GitHub Actions roda **automaticamente a cada hora** de segunda a sábado.
Você também pode forçar uma atualização manualmente em:
**GitHub → Actions → Atualizar PIX Doutores → Run workflow**

---

## 🔒 Segurança

- As credenciais (`MANUS` / `MANUS2026`) ficam salvas como **Secrets** no GitHub
- Nunca aparecem no código nem nos logs
- O repositório pode ser **privado** para ninguém mais ver seus dados

---

## ⚠️ Possíveis ajustes no scraper

O arquivo `scripts/scraper.py` tenta navegar pelo menu do sistema automaticamente.
Caso alguma cidade não funcione, o scraper pula e tenta as próximas — você verá
no log do Actions quais cidades tiveram erro.

Se precisar ajustar a navegação para uma cidade específica, abra um issue ou
consulte o log de erros em **Actions → último run → logs**.
