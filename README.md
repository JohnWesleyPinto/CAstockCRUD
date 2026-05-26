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
cd /CAstockCRUD
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
