# CAStock 📦 - Sistema Inteligente de Gestão de Estoque e Vendas

**CAStock** é uma plataforma moderna e responsiva para controle de estoque, registro de vendas (PDV) e auditoria operacional. O sistema destaca-se por incorporar **inteligência artificial (Gemini API)** e **modelos matemáticos (Cadeias de Markov)** para análise preditiva de demanda e riscos de ruptura de estoque.

O projeto foi inteiramente desenhado para o **Light Mode (Tema Claro)** nativo de alto contraste, garantindo excelente legibilidade e usabilidade profissional.

---

## 🚀 Principais Funcionalidades

- **PDV Dinâmico (Frente de Caixa)**: Realize vendas de forma ágil com pesquisa instantânea de produtos, baixa automática no estoque e cálculo imediato de faturamento e lucro líquido em tempo real.
- **Previsão Inteligente (Markov & Monte Carlo)**:
  - Estima o tempo de vida útil restante dos produtos no estoque (dias para ruptura).
  - Calcula a probabilidade percentual de desabastecimento nos próximos 7 dias.
  - Sugere automaticamente o lote ideal de compra para reposição saudável de estoque.
  - Implementa **Suavização de Laplace (Laplace Smoothing)** na matriz de transições de vendas diárias para evitar estados absorventes artificiais.
- **CAStockBot (Assistente de IA)**: Chatbot integrado com o modelo **Gemini 3.5 Flash** e recurso de **Function Calling** automático.
  - Conecta-se de forma ativa e segura ao banco de dados do Django.
  - Responde sobre faturamento, produtos críticos e buscas gerais de forma conversacional.
  - Possui um **Modo de Simulação Local (Rule-Based)** de fallback caso nenhuma chave de API do Gemini esteja configurada.
- **Painel de Gestão de Membros**: Administradores podem gerenciar operadores de caixa e alterar permissões de acesso granulares (Visualizar Dashboard, Cadastrar Vendas, Editar Produtos, Excluir Produtos, etc.) por meio de switches instantâneos que utilizam **HTMX**.
- **Logs e Auditoria**: Registro transparente de ações administrativas, logins e operações críticas do sistema.

---

## 🛠️ Tecnologias Utilizadas

- **Core**: [Python 3.12](https://www.python.org/) & [Django 6](https://www.djangoproject.com/)
- **Interface Visual**: HTML5, Vanilla CSS, [TailwindCSS](https://tailwindcss.com/) & [DaisyUI](https://daisyui.com/) (Light Mode Nativo)
- **Dinamismo no Front-end**: [Alpine.js](https://alpinejs.dev/) & [HTMX](https://htmx.org/) (submissões sem recarregar a tela)
- **Integração de IA**: Google Generative AI Python SDK (Gemini API)
- **Banco de Dados**: SQLite (desenvolvimento/local) e PostgreSQL (opcional para produção)

---

## 📦 Como Instalar e Rodar Localmente

### 1. Requisitos Prévios
- Ter o **Python 3.10+** instalado.
- Ter o gerenciador de pacotes **pip** atualizado.

### 2. Clonar o Repositório e Configurar Ambiente
```bash
# Clone o projeto
git clone https://github.com/JohnWesleyPinto/CAStock.git
cd CAStock

# Crie e ative a virtualenv
python -m venv .venv
source .venv/bin/activate  # No Windows: .venv\Scripts\activate

# Instale as dependências
pip install -r requirements.txt
```

### 3. Configurar Variáveis de Ambiente
Copie o arquivo de exemplo `.env.example` para `.env`:
```bash
cp .env.example .env
```
Abra o arquivo `.env` e ajuste as variáveis. Se quiser rodar a IA avançada do Gemini, configure a chave `GEMINI_API_KEY`:
```env
DEBUG=True
SECRET_KEY=sua-chave-secreta-django
GEMINI_API_KEY=AIzaSy... (opcional)
```

### 4. Rodar Migrações e Criar Superusuário (Admin)
```bash
python manage.py migrate
python manage.py createsuperuser
```

### 5. Alimentar o Histórico de Vendas (Seeding)
Para rodar as estatísticas de Markov imediatamente, alimente o sistema com o histórico simulado de vendas diárias e produtos:
```bash
python manage.py seed_sales_history
```
*Esse comando cadastra produtos como Pippos, Coca Cola, Água Mineral, Biscoito, Red Bull, etc., e cria um histórico rico de vendas nos últimos 30 dias para calibrar a Cadeia de Markov.*

### 6. Iniciar o Servidor
```bash
python manage.py runserver
```
Acesse o painel em: **[http://127.0.0.1:8000](http://127.0.0.1:8000)**.

---

## 🧪 Executar Testes Unitários

Para validar a integridade das regras de negócio do PDV, baixas em estoque e restrições de permissão administrativa:
```bash
python manage.py test
```

---

## 🌐 Hospedagem (Deploy)

### Opção A: PythonAnywhere (Recomendado para SQLite)
O **PythonAnywhere** é excelente por manter o banco local SQLite persistido sem custos extras. 
1. Crie uma conta gratuita e clone seu projeto via Console Bash.
2. Crie a virtualenv e instale as dependências.
3. Configure uma Web App informando o diretório de código do projeto, o virtualenv e aponte os arquivos estáticos para `/home/seuusuario/CAStock/staticfiles`.
4. Configure o arquivo `wsgi.py` no painel do PythonAnywhere e dê Reload.

### Opção B: Render + Neon (Recomendado para PostgreSQL)
1. Crie um banco PostgreSQL serverless gratuito no **[Neon.tech](https://neon.tech/)**.
2. Hospede a aplicação no **[Render.com](https://render.com/)** como um *Web Service* conectado ao seu GitHub.
3. Defina as variáveis no painel da Render:
   - `DEBUG` = `False`
   - `DATABASE_URL` = `sua-url-de-conexao-do-neon`
   - `ALLOWED_HOSTS` = `seu-app.onrender.com`
4. O Render executará o script de build (`pip install`, `migrate` e `collectstatic`) e subirá o processo de produção com `gunicorn castock_project.wsgi:application`.
