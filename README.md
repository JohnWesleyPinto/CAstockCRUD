# CAStock 🍷📦

O **CAStock** é um sistema de gerenciamento e vendas de produtos moderno, minimalista, seguro e de alta performance desenvolvido especialmente para as conveniências de Centros Acadêmicos (C.A.). A aplicação possui uma interface SPA (Single Page Application) responsiva com estética premium baseada na paleta de cores Vinho & Branco.

---

## 🚀 Funcionalidades Principais

* **Segurança Robusta:** Senhas salvas com hash criptográfico `bcrypt` e rotas operacionais protegidas por autenticação baseada em tokens JWT (`PyJWT`).
* **Operação de Vendas Consistente:** Registro transacional de vendas com validação rigorosa de estoque.
* **Calculadora em Tempo Real:** Cálculo instantâneo do valor total da venda no formulário de saída.
* **Badges de Alerta de Estoque:** Indicação visual inteligente de status de produtos:
  - `Disponível` (estoque > 5 unidades)
  - `Estoque Baixo` (estoque entre 1 e 5 unidades)
  - `Esgotado` (estoque == 0 unidades)
* **Single Page Application (SPA) Premium:** Transições de tela fluidas, alertas flutuantes (toasts) dinâmicos e carregamento otimizado.

---

## 🛠️ Stack Tecnológica

* **Back-End:** Python 3.12+ utilizando o framework **FastAPI** (rápido, tipado e com documentação Swagger interativa gerada automaticamente em `/docs`).
* **Banco de Dados:** **SQLite** persistido localmente no arquivo `castock.db` usando o ORM **SQLAlchemy**.
* **Front-End:** HTML5 semântico, CSS3 customizado (sem frameworks pesados) e JavaScript Vanilla assíncrono.

---

## 💻 Como Executar Localmente

Siga o passo a passo abaixo para rodar a aplicação em sua máquina local:

### 1. Clonar ou Acessar a Pasta do Projeto
Certifique-se de estar na pasta raiz do projeto onde os arquivos estão localizados:
```bash
cd /home/john/Desktop/ESTUDO_PESSOAL/CAstockCRUD/CAstockCRUD
```

### 2. Criar e Ativar o Ambiente Virtual (Virtualenv)
Recomendado para manter as dependências do Python isoladas:
```bash
# Criar o ambiente virtual (.venv)
python3 -m venv .venv

# Ativar o ambiente virtual
source .venv/bin/activate
```

### 3. Instalar as Dependências do Projeto
Instale as bibliotecas necessárias declaradas no arquivo `requirements.txt`:
```bash
pip install -r requirements.txt
```

### 4. Executar o Servidor FastAPI
Inicie a aplicação utilizando o **Uvicorn** com recarga automática de desenvolvimento (hot-reload):
```bash
python3 main.py
```
Ou alternativamente via CLI:
```bash
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

### 5. Acessar a Aplicação
Abra seu navegador favorito e acesse:
* **Interface do CAStock (Frontend SPA):** [http://127.0.0.1:8000](http://127.0.0.1:8000)
* **Documentação Interativa (Swagger):** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 🚀 Guia de Hospedagem em Produção

Você pode hospedar essa aplicação completa com SQLite de forma totalmente gratuita! Veja como configurar em duas das principais plataformas modernas:

### Opção A: Hospedagem no Render.com

O Render permite subir projetos Python diretamente do GitHub e oferece bancos SQLite locais de alta velocidade.

1. **Crie uma Conta** no site [Render.com](https://render.com) (conecte com o seu GitHub).
2. **Crie um Novo Serviço:**
   - No painel do Render, clique em **New +** e selecione **Web Service**.
   - Conecte o repositório Git onde subiu os arquivos deste projeto.
3. **Configure as Informações de Build & Deploy:**
   - **Name:** `castock` (ou outro de sua preferência)
   - **Region:** Escolha a mais próxima (ex: `Oregon (US West)` ou `Frankfurt`)
   - **Branch:** `main` (ou correspondente)
   - **Language/Runtime:** `Python`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. **⚠️ IMPORTANTE: Persistência do Banco SQLite no Render**
   Como os containers do Render têm discos efêmeros (são reiniciados e limpam dados salvos a cada deploy), você precisa montar um **Disco Persistente (Render Disk)** para que as contas e produtos não sumam:
   - Role a página até a seção **Advanced**.
   - Adicione uma **Environment Variable** (Variável de Ambiente) se desejar customizar sua chave secreta do JWT:
     - `JWT_SECRET_KEY` = `sua-chave-secreta-altamente-segura`
   - Clique em **Add Disk**:
     - **Name:** `castock_data`
     - **Mount Path:** `/var/data`
     - **Size:** `1 GB` (suficiente para milhares de registros SQLite).
   - Configure o back-end para ler a base de dados na pasta persistente. No `main.py`, mude a linha da URL de conexão para ler na pasta do disco montado:
     `DATABASE_URL = "sqlite:////var/data/castock.db"` (nota: se quiser manter compatibilidade local, você pode usar uma variável de ambiente no Render `DATABASE_URL` contendo `sqlite:////var/data/castock.db` e ler no Python via `os.getenv("DATABASE_URL", "sqlite:///./castock.db")`).
5. **Clique em Create Web Service** e aguarde a finalização da build!

---

### Opção B: Hospedagem no Railway.app

O Railway é uma excelente plataforma com configuração instantânea e suporte nativo a volumes persistentes.

1. **Crie uma Conta** no site [Railway.app](https://railway.app) usando sua conta do GitHub.
2. **Crie um Novo Projeto:**
   - Clique em **New Project** -> **Deploy from GitHub repository**.
   - Selecione o repositório do CAStock.
3. **Variáveis de Ambiente:**
   - No painel da aplicação, acesse a aba **Variables** e configure:
     - `PORT` = `8000`
     - `JWT_SECRET_KEY` = `sua-chave-super-secreta`
     - `DATABASE_URL` = `sqlite:///data/castock.db`
4. **⚠️ IMPORTANTE: Adicionar Volume de Persistência no Railway**
   - No painel do seu serviço Railway, clique em **Settings**.
   - Procpe por **Volumes** e clique em **Add Volume**.
   - **Mount Path:** `/app/data` (ou `/data` conforme configurado na sua variável `DATABASE_URL`).
   - Salve as alterações. O Railway irá reinstalar a aplicação vinculando o banco SQLite de forma permanente.
5. **Acesso:**
   - Acesse a aba **Settings** e em **Public Networking** clique em **Generate Domain**. Prontinho! Seu sistema CAStock estará online.
