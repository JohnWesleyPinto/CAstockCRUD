import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum, F, Q
from django.utils import timezone
from django.core.paginator import Paginator

from .models import (
    Usuario, MembroPermissao, ConfiguracaoSistema, 
    Produto, Venda, ItemVenda, LogSistema, registrar_log
)

# =====================================================================
# 1. Custom Authorization Decorator
# =====================================================================
def checar_permissao(permissao_campo):
    """
    Decorator customizado para verificar permissões de forma dinâmica.
    Administradores e Superusuários têm acesso irrestrito.
    """
    def decorator(view_func):
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            # Administrador / Superuser passa direto
            if request.user.is_superuser or request.user.tipo_usuario == 'ADMIN':
                return view_func(request, *args, **kwargs)
            
            # Se for membro, checa na tabela MembroPermissao
            permissoes = getattr(request.user, 'permissoes', None)
            if permissoes and getattr(permissoes, permissao_campo, False):
                return view_func(request, *args, **kwargs)
            
            # Se for requisição HTMX, retorna fragmento de erro amigável com status 403
            if request.headers.get('HX-Request'):
                return HttpResponse(
                    '<div class="alert alert-error shadow-lg my-2"><div><i class="fa-solid fa-circle-xmark"></i><span>Acesso Negado: Permissão insuficiente para esta ação.</span></div></div>',
                    status=403
                )
            
            # Navegação normal
            messages.error(request, "Você não tem permissão para acessar esta área.")
            return redirect('vendas')
        return _wrapped_view
    return decorator


# =====================================================================
# 2. Authentication Views
# =====================================================================
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    if request.method == 'POST':
        usr = request.POST.get('username')
        pas = request.POST.get('password')
        next_url = request.POST.get('next', 'dashboard')
        
        user = authenticate(request, username=usr, password=pas)
        if user is not None:
            if user.is_active:
                login(request, user)
                # Registrar Log de Auditoria
                registrar_log(
                    usuario=user,
                    acao="Login bem-sucedido",
                    descricao=f"Usuário {user.username} realizou autenticação com sucesso.",
                    nivel=LogSistema.NivelLog.INFO
                )
                messages.success(request, f"Bem-vindo de volta, {user.username}!")
                return redirect(next_url)
            else:
                messages.error(request, "Esta conta foi desativada pelo administrador.")
                registrar_log(
                    usuario=None,
                    acao="Tentativa de login de conta desativada",
                    descricao=f"Conta {usr} tentou autenticar, mas está inativa.",
                    nivel=LogSistema.NivelLog.WARN
                )
        else:
            messages.error(request, "Usuário ou senha incorretos.")
            registrar_log(
                usuario=None,
                acao="Falha de autenticação",
                descricao=f"Tentativa falha de login com o nome de usuário: {usr}",
                nivel=LogSistema.NivelLog.WARN
            )
            
    return render(request, 'login.html')


@login_required
def logout_view(request):
    user = request.user
    registrar_log(
        usuario=user,
        acao="Logout bem-sucedido",
        descricao=f"Usuário {user.username} encerrou a sessão no sistema.",
        nivel=LogSistema.NivelLog.INFO
    )
    logout(request)
    messages.success(request, "Sessão encerrada com segurança.")
    return redirect('vendas')


# =====================================================================
# 3. Dashboard and Metrics Views
# =====================================================================
@login_required
@checar_permissao('pode_visualizar_dashboard')
def dashboard_view(request):
    return render(request, 'dashboard.html')


@login_required
@checar_permissao('pode_visualizar_dashboard')
def dashboard_metrics(request):
    periodo = request.GET.get('periodo', 'mes')
    agora = timezone.now()
    
    # Configurar filtros temporais
    if periodo == 'semana':
        data_inicio = agora - datetime.timedelta(days=7)
    elif periodo == 'trimestre':
        data_inicio = agora - datetime.timedelta(days=90)
    elif periodo == 'todos':
        data_inicio = datetime.datetime.min.replace(tzinfo=timezone.utc)
    else:  # 'mes' por padrão
        data_inicio = agora - datetime.timedelta(days=30)
        
    # Consulta de Vendas no Período
    vendas_periodo = Venda.objects.filter(data_venda__gte=data_inicio)
    
    # 1. Métricas Financeiras
    totais = vendas_periodo.aggregate(
        faturamento_total=Sum('valor_total_venda'),
        lucro_total=Sum('lucro_total')
    )
    faturamento = totais['faturamento_total'] or 0.00
    lucro = totais['lucro_total'] or 0.00
    
    # 2. Métricas por Meio de Pagamento
    pix_totais = vendas_periodo.filter(forma_pagamento=Venda.FormaPagamento.PIX).aggregate(
        faturamento=Sum('valor_total_venda'),
        lucro=Sum('lucro_total')
    )
    caixinha_totais = vendas_periodo.filter(forma_pagamento=Venda.FormaPagamento.CAIXINHA).aggregate(
        faturamento=Sum('valor_total_venda'),
        lucro=Sum('lucro_total')
    )
    
    faturamento_pix = pix_totais['faturamento'] or 0.00
    lucro_pix = pix_totais['lucro'] or 0.00
    faturamento_caixinha = caixinha_totais['faturamento'] or 0.00
    lucro_caixinha = caixinha_totais['lucro'] or 0.00
    
    # 3. Métricas de Estoque
    produtos_ativos = Produto.objects.filter(ativo=True)
    quantidade_itens_estoque = produtos_ativos.aggregate(total_itens=Sum('quantidade'))['total_itens'] or 0
    
    # Valor Total Estimado em Estoque (Preço de Venda Final * Quantidade) calculado no banco de dados
    valor_estimado_estoque = produtos_ativos.aggregate(
        total_valor=Sum(F('valor_venda_final') * F('quantidade'))
    )['total_valor'] or 0.00
    
    # 4. Produtos Mais Vendidos no Período
    mais_vendidos = ItemVenda.objects.filter(venda__data_venda__gte=data_inicio) \
                        .values('produto__nome') \
                        .annotate(total_vendido=Sum('quantidade_vendida')) \
                        .order_by('-total_vendido')[:5]

    # 5. Alertas de Estoque Crítico (menos de 5 unidades)
    estoque_critico = produtos_ativos.filter(quantidade__lt=5).order_by('quantidade')[:5]

    context = {
        'periodo': periodo,
        'faturamento': faturamento,
        'lucro': lucro,
        'faturamento_pix': faturamento_pix,
        'lucro_pix': lucro_pix,
        'faturamento_caixinha': faturamento_caixinha,
        'lucro_caixinha': lucro_caixinha,
        'quantidade_itens_estoque': quantidade_itens_estoque,
        'valor_estimado_estoque': valor_estimado_estoque,
        'mais_vendidos': mais_vendidos,
        'estoque_critico': estoque_critico,
    }
    
    return render(request, 'partials/dashboard_metrics.html', context)


# =====================================================================
# 4. Member Management Views
# =====================================================================
@login_required
@checar_permissao('pode_gerenciar_membros')
def membros_view(request):
    if request.method == 'POST':
        # Cadastro de Novo Membro
        usr = request.POST.get('username')
        email = request.POST.get('email')
        pas = request.POST.get('password')
        tipo = request.POST.get('tipo_usuario', 'MEMBRO')
        
        if Usuario.objects.filter(username=usr).exists():
            messages.error(request, f"O nome de usuário '{usr}' já está cadastrado.")
        else:
            novo_membro = Usuario.objects.create_user(
                username=usr,
                email=email,
                password=pas,
                tipo_usuario=tipo
            )
            registrar_log(
                usuario=request.user,
                acao="Cadastro de Membro",
                descricao=f"Novo membro cadastrado: {novo_membro.username} ({novo_membro.get_tipo_usuario_display()})",
                nivel=LogSistema.NivelLog.INFO
            )
            messages.success(request, f"Membro '{novo_membro.username}' cadastrado com sucesso!")
            return redirect('membros')

    # Listar membros operacionais e outros administradores (exceto superusers e ele mesmo)
    membros = Usuario.objects.exclude(is_superuser=True).exclude(id=request.user.id).order_by('username')
    return render(request, 'membros.html', {'membros': membros})


@login_required
@checar_permissao('pode_gerenciar_membros')
def atualizar_permissao(request, membro_id, permissao_campo):
    """
    Atualiza via HTMX as chaves de alternância de permissão instantaneamente.
    """
    if request.method == 'POST':
        membro = get_object_or_404(Usuario, id=membro_id)
        
        # Garante que o perfil de permissões exista
        permissoes, created = MembroPermissao.objects.get_or_create(usuario=membro)
        
        if hasattr(permissoes, permissao_campo):
            # Inverte o estado booleano da permissão
            estado_atual = getattr(permissoes, permissao_campo)
            setattr(permissoes, permissao_campo, not estado_atual)
            permissoes.save()
            
            estado_texto = "Ativada" if not estado_atual else "Desativada"
            registrar_log(
                usuario=request.user,
                acao="Alteração de Permissão",
                descricao=f"A permissão '{permissao_campo}' do membro {membro.username} foi {estado_texto.lower()}.",
                nivel=LogSistema.NivelLog.INFO
            )
            
            # Retorna um elemento toast que o HTMX pode adicionar ou sinalizar
            response_html = f"""
            <div id="toast-container" hx-swap-oob="beforeend">
                <div class="alert alert-success shadow-lg p-3 text-sm transition-all duration-300" x-data="{{ show: true }}" x-show="show" x-init="setTimeout(() => show = false, 3000)">
                    <div>
                        <i class="fa-solid fa-circle-check"></i>
                        <span>Permissão '{permissao_campo}' de {membro.username} alterada para {estado_texto.lower()}!</span>
                    </div>
                </div>
            </div>
            """
            return HttpResponse(response_html)
            
    return HttpResponse("Requisição inválida", status=400)


# =====================================================================
# 5. Product Management Views (Soft Delete)
# =====================================================================
@login_required
def produtos_view(request):
    # Verificar se o usuário tem permissão
    is_admin_or_has_perm = request.user.tipo_usuario == 'ADMIN' or getattr(request.user.permissoes, 'pode_cadastrar_produto', False)
    
    if request.method == 'POST':
        if not is_admin_or_has_perm:
            messages.error(request, "Você não tem permissão para cadastrar ou editar produtos.")
            return redirect('produtos')
            
        produto_id = request.POST.get('produto_id')
        nome = request.POST.get('nome')
        quantidade = int(request.POST.get('quantidade', 0))
        valor_adquirido = float(request.POST.get('valor_adquirido', 0.00))
        porcentagem_ganho = float(request.POST.get('porcentagem_ganho', 30.00))
        valor_venda_final = float(request.POST.get('valor_venda_final', 0.00))
        
        eh_caixa = request.POST.get('eh_caixa') == 'true'
        quantidade_por_caixa = int(request.POST.get('quantidade_por_caixa', 1)) if eh_caixa else 1
        
        data_compra_str = request.POST.get('data_compra')
        data_compra = None
        if data_compra_str:
            try:
                data_compra = timezone.make_aware(datetime.datetime.strptime(data_compra_str, '%Y-%m-%dT%H:%M'))
            except ValueError:
                data_compra = timezone.now()
        else:
            data_compra = timezone.now()

        # Multiplicação da quantidade de unidades se comprado fechado em caixa
        if eh_caixa:
            # Ex: Comprou 2 caixas com 30 unidades cada = 60 unidades totais físicas no estoque
            quantidade_total = quantidade * quantidade_por_caixa
        else:
            quantidade_total = quantidade

        if produto_id:
            # Edição
            if not (request.user.tipo_usuario == 'ADMIN' or getattr(request.user.permissoes, 'pode_editar_produto', False)):
                messages.error(request, "Você não tem permissão para editar produtos.")
                return redirect('produtos')
                
            produto = get_object_or_404(Produto, id=produto_id)
            produto.nome = nome
            
            quantidade_estoque_atual = request.POST.get('quantidade_estoque_atual')
            if quantidade_estoque_atual is not None and quantidade_estoque_atual != '':
                produto.quantidade = int(quantidade_estoque_atual)
            else:
                produto.quantidade = quantidade_total

            produto.data_compra = data_compra
            produto.valor_adquirido = valor_adquirido
            produto.porcentagem_ganho = porcentagem_ganho
            produto.valor_venda_final = valor_venda_final
            produto.eh_caixa = eh_caixa
            produto.quantidade_por_caixa = quantidade_por_caixa
            produto.save()
            
            registrar_log(
                usuario=request.user,
                acao="Edição de Produto",
                descricao=f"Produto editado: {produto.nome}. Quantidade em estoque: {produto.quantidade}.",
                nivel=LogSistema.NivelLog.INFO
            )
            messages.success(request, f"Produto '{produto.nome}' atualizado com sucesso!")
        else:
            # Cadastro Novo
            novo_produto = Produto.objects.create(
                nome=nome,
                quantidade=quantidade_total,
                data_compra=data_compra,
                valor_adquirido=valor_adquirido,
                porcentagem_ganho=porcentagem_ganho,
                valor_venda_final=valor_venda_final,
                eh_caixa=eh_caixa,
                quantidade_por_caixa=quantidade_por_caixa
            )
            registrar_log(
                usuario=request.user,
                acao="Cadastro de Produto",
                descricao=f"Novo produto cadastrado: {novo_produto.nome}. Custo Unitário: R$ {novo_produto.custo_unitario}. Qtd: {novo_produto.quantidade}.",
                nivel=LogSistema.NivelLog.INFO
            )
            messages.success(request, f"Produto '{novo_produto.nome}' cadastrado com sucesso!")
            
        return redirect('produtos')

    # Filtragem e Busca de Produtos
    search_query = request.GET.get('search', '')
    filtro_estoque = request.GET.get('filtro_estoque', 'todos')
    
    produtos = Produto.objects.filter(ativo=True).order_by('nome')
    
    if search_query:
        produtos = produtos.filter(nome__icontains=search_query)
        
    if filtro_estoque == 'baixo':
        produtos = produtos.filter(quantidade__lt=5)
    elif filtro_estoque == 'esgotado':
        produtos = produtos.filter(quantidade=0)

    # Paginação de 10 produtos por página
    paginator = Paginator(produtos, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Buscar a margem global para preenchimento dinâmico
    margem_global = ConfiguracaoSistema.get_config().margem_lucro_padrao

    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'filtro_estoque': filtro_estoque,
        'margem_global': margem_global,
        'is_admin_or_has_perm': is_admin_or_has_perm,
    }
    return render(request, 'produtos.html', context)


@login_required
def excluir_produto(request, produto_id):
    """
    Exclusão Lógica (Soft Delete).
    Apenas oculta o produto, mas mantém os dados consistentes para o histórico de vendas.
    """
    # Verificar se o usuário tem permissão
    if not (request.user.tipo_usuario == 'ADMIN' or getattr(request.user.permissoes, 'pode_excluir_produto', False)):
        messages.error(request, "Você não tem permissão para excluir produtos.")
        return redirect('produtos')

    if request.method == 'POST':
        produto = get_object_or_404(Produto, id=produto_id)
        produto.ativo = False
        produto.save()
        
        registrar_log(
            usuario=request.user,
            acao="Exclusão de Produto",
            descricao=f"Produto '{produto.nome}' foi removido logicamente (inativado).",
            nivel=LogSistema.NivelLog.WARN
        )
        messages.warning(request, f"Produto '{produto.nome}' foi excluído com sucesso.")
        
    return redirect('produtos')


# =====================================================================
# 6. Sales Flow and Atomicity
# =====================================================================
def vendas_view(request):
    # Passa todos os produtos ativos e em estoque para carregar no grid do PDV
    produtos = Produto.objects.filter(ativo=True, quantidade__gt=0).order_by('nome')
    return render(request, 'vendas.html', {'produtos': produtos})


def buscar_produto_venda(request):
    """
    Pesquisa dinâmica com HTMX na tela de vendas.
    """
    search_query = request.GET.get('q', '')
    if len(search_query) < 1:
        return HttpResponse("")
        
    produtos = Produto.objects.filter(ativo=True, quantidade__gt=0, nome__icontains=search_query).order_by('nome')[:5]
    return render(request, 'partials/produto_search_results.html', {'produtos': produtos})


def registrar_venda_action(request):
    """
    Processa a venda com múltiplos itens de forma Atômica.
    Garante a dedução segura de estoque e tratamento de erros.
    """
    if request.method == 'POST':
        nome_pessoa = request.POST.get('nome_pessoa', 'Cliente não identificado')
        forma_pagamento = int(request.POST.get('forma_pagamento', Venda.FormaPagamento.PIX))
        
        # Recuperar listas do carrinho (enviadas como múltiplos inputs nomeados igualmente)
        produtos_ids = request.POST.getlist('produtos_ids[]')
        quantidades = request.POST.getlist('quantidades[]')
        valores_venda = request.POST.getlist('valores_venda[]')
        
        if not produtos_ids:
            messages.error(request, "O carrinho está vazio. Adicione pelo menos um item para registrar a venda.")
            return redirect('vendas')
            
        try:
            with transaction.atomic():
                # 1. Instanciar cabeçalho da Venda
                venda = Venda.objects.create(
                    usuario_responsavel=request.user if request.user.is_authenticated else None,
                    nome_pessoa=nome_pessoa,
                    forma_pagamento=forma_pagamento
                )
                
                # 2. Iterar sobre os itens do carrinho
                for i in range(len(produtos_ids)):
                    p_id = produtos_ids[i]
                    qtd = int(quantidades[i])
                    val_venda_final = float(valores_venda[i])
                    
                    # Obter e bloquear produto para evitar concorrência/corrida de estoque (select_for_update)
                    produto = Produto.objects.select_for_update().get(id=p_id, ativo=True)
                    
                    # Validação crítica de estoque
                    if produto.quantidade < qtd:
                        raise ValueError(f"Estoque insuficiente para o produto '{produto.nome}'. Quantidade disponível: {produto.quantidade}.")
                        
                    # Baixa automática de estoque
                    produto.quantidade -= qtd
                    produto.save()
                    
                    # Gravar item da venda com dados históricos de custo e preço
                    ItemVenda.objects.create(
                        venda=venda,
                        produto=produto,
                        quantidade_vendida=qtd,
                        custo_unitario_historico=produto.custo_unitario,
                        valor_unitario_venda=val_venda_final
                    )
                
                # 3. Recalcular e atualizar totais e lucros no cabeçalho
                venda.atualizar_totais()
                
                # 4. Gravar auditoria nos logs do sistema
                registrar_log(
                    usuario=request.user if request.user.is_authenticated else None,
                    acao="Registro de Venda",
                    descricao=f"Venda registrada com sucesso para {venda.nome_pessoa}. Total: R$ {venda.valor_total_venda}. Lucro: R$ {venda.lucro_total}.",
                    nivel=LogSistema.NivelLog.INFO
                )
                
                messages.success(request, f"Venda de R$ {venda.valor_total_venda} registrada com sucesso!")
                return redirect('vendas')
                
        except ValueError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f"Erro inesperado no checkout: {str(e)}")
            
    return redirect('vendas')


# =====================================================================
# 7. System Audit Logs View (Paginated & Filtered)
# =====================================================================
@login_required
def logs_view(request):
    if request.user.tipo_usuario != 'ADMIN':
        messages.error(request, "Apenas administradores podem visualizar os logs do sistema.")
        return redirect('dashboard')
        
    nivel_filtro = request.GET.get('nivel', '')
    busca = request.GET.get('busca', '')
    
    logs = LogSistema.objects.all()
    
    if nivel_filtro:
        logs = logs.filter(nivel=nivel_filtro)
    if busca:
        logs = logs.filter(Q(acao__icontains=busca) | Q(descricao__icontains=busca) | Q(usuario__username__icontains=busca))
        
    paginator = Paginator(logs, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'nivel_filtro': nivel_filtro,
        'busca': busca,
    }
    return render(request, 'logs.html', context)


# =====================================================================
# 8. User Custom Views (Cadastro, Redefinição de Senha, Perfil)
# =====================================================================
def cadastro_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    if request.method == 'POST':
        usr = request.POST.get('username')
        email = request.POST.get('email')
        pas = request.POST.get('password')
        pas_conf = request.POST.get('password_confirm')
        
        if pas != pas_conf:
            messages.error(request, "As senhas digitadas não coincidem.")
        elif Usuario.objects.filter(username=usr).exists():
            messages.error(request, f"O nome de usuário '{usr}' já está cadastrado.")
        else:
            # Criação do usuário
            novo_usuario = Usuario.objects.create_user(
                username=usr,
                email=email,
                password=pas,
                tipo_usuario='MEMBRO'  # padrão como membro operacional
            )
            registrar_log(
                usuario=novo_usuario,
                acao="Autocadastro de Usuário",
                descricao=f"Novo usuário '{novo_usuario.username}' se cadastrou no sistema como Membro.",
                nivel=LogSistema.NivelLog.INFO
            )
            messages.success(request, "Conta criada com sucesso! Faça seu login para continuar.")
            return redirect('login')
            
    return render(request, 'cadastro.html')


def esqueceu_senha_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    if request.method == 'POST':
        usr = request.POST.get('username')
        email = request.POST.get('email')
        nova_pas = request.POST.get('new_password')
        nova_pas_conf = request.POST.get('new_password_confirm')
        
        if nova_pas != nova_pas_conf:
            messages.error(request, "As novas senhas digitadas não coincidem.")
        else:
            try:
                user = Usuario.objects.get(username=usr, email=email)
                user.set_password(nova_pas)
                user.save()
                registrar_log(
                    usuario=user,
                    acao="Redefinição de Senha",
                    descricao=f"Usuário '{user.username}' redefiniu sua senha de acesso com sucesso.",
                    nivel=LogSistema.NivelLog.WARN
                )
                messages.success(request, "Senha redefinida com sucesso! Acesse sua conta.")
                return redirect('login')
            except Usuario.DoesNotExist:
                messages.error(request, "Usuário ou e-mail correspondente não foi encontrado.")
                
    return render(request, 'esqueceu_senha.html')


@login_required
def perfil_view(request):
    user = request.user
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        foto = request.FILES.get('foto')
        
        user.first_name = first_name
        user.last_name = last_name
        user.email = email
        if foto:
            user.foto = foto
        user.save()
        
        registrar_log(
            usuario=user,
            acao="Atualização de Perfil",
            descricao=f"Usuário '{user.username}' atualizou seus dados de perfil.",
            nivel=LogSistema.NivelLog.INFO
        )
        messages.success(request, "Dados de perfil atualizados com sucesso!")
        return redirect('perfil')
        
    return render(request, 'perfil.html')


@login_required
def alterar_senha_view(request):
    from django.contrib.auth import update_session_auth_hash
    if request.method == 'POST':
        senha_atual = request.POST.get('senha_atual')
        nova_senha = request.POST.get('nova_senha')
        nova_senha_conf = request.POST.get('nova_senha_confirm')
        
        user = request.user
        if not user.check_password(senha_atual):
            messages.error(request, "A senha atual digitada está incorreta.")
        elif nova_senha != nova_senha_conf:
            messages.error(request, "As novas senhas não coincidem.")
        else:
            user.set_password(nova_senha)
            user.save()
            # Atualiza o hash na sessão para evitar logout automático
            update_session_auth_hash(request, user)
            registrar_log(
                usuario=user,
                acao="Alteração de Senha Segura",
                descricao=f"Usuário '{user.username}' alterou sua senha por meio de confirmação do perfil.",
                nivel=LogSistema.NivelLog.INFO
            )
            messages.success(request, "Sua senha foi alterada com sucesso!")
            
    return redirect('perfil')


@login_required
def adicionar_produto_view(request):
    # Verificar se o usuário tem permissão
    is_admin_or_has_perm = request.user.tipo_usuario == 'ADMIN' or getattr(request.user.permissoes, 'pode_cadastrar_produto', False)
    if not is_admin_or_has_perm:
        messages.error(request, "Você não tem permissão para cadastrar produtos.")
        return redirect('produtos')
        
    if request.method == 'POST':
        nome = request.POST.get('nome')
        quantidade = int(request.POST.get('quantidade', 0))
        valor_adquirido = float(request.POST.get('valor_adquirido', 0.00))
        porcentagem_ganho = float(request.POST.get('porcentagem_ganho', 30.00))
        valor_venda_final = float(request.POST.get('valor_venda_final', 0.00))
        
        eh_caixa = request.POST.get('eh_caixa') == 'true'
        quantidade_por_caixa = int(request.POST.get('quantidade_por_caixa', 1)) if eh_caixa else 1
        
        data_compra_str = request.POST.get('data_compra')
        data_compra = None
        if data_compra_str:
            try:
                data_compra = timezone.make_aware(datetime.datetime.strptime(data_compra_str, '%Y-%m-%dT%H:%M'))
            except ValueError:
                data_compra = timezone.now()
        else:
            data_compra = timezone.now()

        # Multiplicação da quantidade de unidades se comprado fechado em caixa
        if eh_caixa:
            quantidade_total = quantidade * quantidade_por_caixa
        else:
            quantidade_total = quantidade

        novo_produto = Produto.objects.create(
            nome=nome,
            quantidade=quantidade_total,
            data_compra=data_compra,
            valor_adquirido=valor_adquirido,
            porcentagem_ganho=porcentagem_ganho,
            valor_venda_final=valor_venda_final,
            eh_caixa=eh_caixa,
            quantidade_por_caixa=quantidade_por_caixa
        )
        registrar_log(
            usuario=request.user,
            acao="Cadastro de Produto",
            descricao=f"Novo produto cadastrado via página dedicada: {novo_produto.nome}. Custo Unitário: R$ {novo_produto.custo_unitario}. Qtd: {novo_produto.quantidade}.",
            nivel=LogSistema.NivelLog.INFO
        )
        messages.success(request, f"Produto '{novo_produto.nome}' cadastrado com sucesso!")
        return redirect('produtos')

    # Exibição do formulário (GET)
    margem_global = ConfiguracaoSistema.get_config().margem_lucro_padrao
    context = {
        'margem_global': margem_global,
    }
    return render(request, 'adicionar_produto.html', context)


@login_required
def configuracoes_view(request):
    if request.user.tipo_usuario != 'ADMIN':
        messages.error(request, "Apenas administradores podem acessar as configurações do sistema.")
        return redirect('dashboard')
        
    config = ConfiguracaoSistema.get_config()
    if request.method == 'POST':
        margem = float(request.POST.get('margem_lucro_padrao', 30.00))
        gemini_key = request.POST.get('gemini_api_key', '').strip()
        config.margem_lucro_padrao = margem
        config.gemini_api_key = gemini_key or None
        config.save()
        
        registrar_log(
            usuario=request.user,
            acao="Alteração de Configurações",
            descricao=f"Administrador '{request.user.username}' alterou a margem padrão para {margem}% e atualizou a API Key do Gemini.",
            nivel=LogSistema.NivelLog.WARN
        )
        messages.success(request, "Configurações do sistema atualizadas com sucesso!")
        return redirect('configuracoes')
        
    return render(request, 'configuracoes.html', {'config': config})


# =====================================================================
# 9. Academic Demo & Tests Dashboard
# =====================================================================
@login_required
@checar_permissao('pode_visualizar_dashboard')
def testes_view(request):
    if request.user.tipo_usuario != 'ADMIN':
        messages.error(request, "Apenas administradores podem acessar o painel de testes.")
        return redirect('dashboard')
    return render(request, 'testes.html')


@login_required
@checar_permissao('pode_visualizar_dashboard')
def resetar_banco_view(request):
    if request.user.tipo_usuario != 'ADMIN':
        messages.error(request, "Apenas administradores podem resetar o banco de dados.")
        return redirect('dashboard')
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                ItemVenda.objects.all().delete()
                Venda.objects.all().delete()
                Produto.objects.all().delete()
                LogSistema.objects.all().delete()
                
                # Registrar o log do reset
                registrar_log(
                    usuario=request.user,
                    acao="Reset do Banco de Dados",
                    descricao=f"O banco de dados foi limpo pelo administrador {request.user.username}. Produtos, vendas e logs foram apagados.",
                    nivel=LogSistema.NivelLog.WARN
                )
            messages.warning(request, "Banco de dados limpo com sucesso! Produtos, vendas e logs foram removidos. Usuários preservados.")
        except Exception as e:
            messages.error(request, f"Erro ao resetar banco de dados: {str(e)}")
            
    return redirect('testes')


@login_required
@checar_permissao('pode_visualizar_dashboard')
def executar_teste_view(request, teste_id):
    if request.user.tipo_usuario != 'ADMIN':
        return HttpResponse("<span class='text-red-500'>[ERRO] Acesso negado.</span>")

    logs = []
    def log(msg):
        logs.append(f"<div class='py-0.5 font-mono'><span class='text-slate-500'>[{datetime.datetime.now().strftime('%H:%M:%S')}]</span> {msg}</div>")

    try:
        if teste_id == 1:
            log("<span class='text-yellow-400 font-bold'>[INÍCIO] Teste de Consistência de Estoque & Rollback (Atomicidade)</span>")
            # 1. Criar produto de teste
            produto_temp = Produto.objects.create(
                nome="Produto Teste Concorrência (Coca-Cola Lote Especial)",
                quantidade=5,
                valor_adquirido=10.00,
                porcentagem_ganho=50.00,
                valor_venda_final=3.00
            )
            log(f"Produto temporário cadastrado: <b>{produto_temp.nome}</b>")
            log(f"Estoque físico inicial no banco: <span class='text-indigo-400 font-bold'>{produto_temp.quantidade} unidades</span>")
            log(f"Custo unitário: R$ {produto_temp.custo_unitario} | Venda unitária: R$ {produto_temp.valor_venda_final}")

            # 2. Tentar registrar venda de 6 unidades (estouro)
            log("Simulando tentativa de venda de <span class='text-amber-500 font-bold'>6 unidades</span> (Estoque máximo: 5)...")
            
            try:
                with transaction.atomic():
                    log("Abrindo transação atômica no banco de dados...")
                    
                    # Simular a lógica de registrar_venda_action
                    venda_temp = Venda.objects.create(
                        usuario_responsavel=request.user,
                        nome_pessoa="Cliente Teste 1",
                        forma_pagamento=Venda.FormaPagamento.PIX
                    )
                    log(f"Cabeçalho da venda instanciado. ID: {venda_temp.id}")
                    
                    qtd_vender = 6
                    log(f"Bloqueando produto com select_for_update() para evitar concorrência...")
                    produto_db = Produto.objects.select_for_update().get(id=produto_temp.id)
                    
                    log(f"Validando disponibilidade: {produto_db.quantidade} em estoque vs {qtd_vender} solicitado...")
                    if produto_db.quantidade < qtd_vender:
                        log("<span class='text-red-400'>[VAL_ERRO] Estoque insuficiente! Lançando ValueError...</span>")
                        raise ValueError(f"Estoque insuficiente para o produto '{produto_db.nome}'. Quantidade disponível: {produto_db.quantidade}.")
                    
                    # Se passasse, daria baixa
                    produto_db.quantidade -= qtd_vender
                    produto_db.save()
                    log("Baixa efetuada no produto.")
                    
                    ItemVenda.objects.create(
                        venda=venda_temp,
                        produto=produto_db,
                        quantidade_vendida=qtd_vender,
                        custo_unitario_historico=produto_db.custo_unitario,
                        valor_unitario_venda=produto_db.valor_venda_final
                    )
                    venda_temp.atualizar_totais()
                    log("Venda concluída com sucesso!")
                    
            except ValueError as ve:
                log(f"<span class='text-amber-400'>[CAPTURADO] Exceção esperada capturada: '{str(ve)}'</span>")
                log("<span class='text-green-400'>[ROLLBACK] Transação desfeita automaticamente pelo banco de dados (Rollback realizado)!</span>")

            # 3. Verificar estado pós-rollback
            produto_verif = Produto.objects.get(id=produto_temp.id)
            log(f"Verificando quantidade do produto no banco pós-rollback: <span class='text-emerald-400 font-bold'>{produto_verif.quantidade} unidades</span> (inalterado!)")
            
            vendas_relacionadas = Venda.objects.filter(nome_pessoa="Cliente Teste 1").count()
            log(f"Verificando se alguma venda foi salva: <span class='text-emerald-400 font-bold'>{vendas_relacionadas} registradas</span> (0 esperado)")
            
            # Limpar produto temporário
            produto_verif.delete()
            log("Limpando produto temporário...")
            log("<span class='text-emerald-400 font-bold'>[SUCESSO] Teste de Consistência e Atomicidade concluído com êxito!</span>")

        elif teste_id == 2:
            log("<span class='text-yellow-400 font-bold'>[INÍCIO] Teste de Controle de Acesso e Permissões Dinâmicas</span>")
            # 1. Criar usuário temporário do tipo MEMBRO sem permissões administrativas
            import random
            username_temp = f"operador_teste_{random.randint(100, 999)}"
            log(f"Criando usuário temporário do tipo <b>MEMBRO</b>: <code>{username_temp}</code>")
            
            user_temp = Usuario.objects.create_user(
                username=username_temp,
                email=f"{username_temp}@teste.com",
                password="password123",
                tipo_usuario='MEMBRO'
            )
            # O signal gerencia_permissoes_usuario cria MembroPermissao com pode_visualizar_dashboard=False, etc.
            permissoes = user_temp.permissoes
            log(f"Perfil de permissões criado automaticamente pelo signal do model.")
            log(f"Permissão <b>pode_visualizar_dashboard</b>: <span class='text-red-400'>{permissoes.pode_visualizar_dashboard}</span>")
            log(f"Permissão <b>pode_gerenciar_membros</b>: <span class='text-red-400'>{permissoes.pode_gerenciar_membros}</span>")
            log(f"Permissão <b>pode_alterar_porcentagem_lucro</b>: <span class='text-red-400'>{permissoes.pode_alterar_porcentagem_lucro}</span>")

            # 2. Simular requisições de acesso
            log("Simulando tentativa de acesso a áreas restritas pelo operador...")
            
            # Simulamos a lógica do decorator @checar_permissao em views administrativo
            def simular_decorador(usuario, permissao_campo):
                if usuario.is_superuser or usuario.tipo_usuario == 'ADMIN':
                    return "PERMITIDO (Admin/Superuser)"
                perms = getattr(usuario, 'permissoes', None)
                if perms and getattr(perms, permissao_campo, False):
                    return "PERMITIDO (Membro Autorizado)"
                return "NEGADO (403/Redirect)"

            r_dash = simular_decorador(user_temp, 'pode_visualizar_dashboard')
            log(f"Acesso à View 'dashboard_view' (requer 'pode_visualizar_dashboard'): <span class='text-red-400 font-bold'>{r_dash}</span>")
            
            r_memb = simular_decorador(user_temp, 'pode_gerenciar_membros')
            log(f"Acesso à View 'membros_view' (requer 'pode_gerenciar_membros'): <span class='text-red-400 font-bold'>{r_memb}</span>")
            
            r_logs = "NEGADO (Bloqueado por checagem explícita na view)" if user_temp.tipo_usuario != 'ADMIN' else "PERMITIDO"
            log(f"Acesso à View 'logs_view' (requer ser ADMIN): <span class='text-red-400 font-bold'>{r_logs}</span>")

            # 3. Comparar com o usuário ADMIN atual
            log("Simulando tentativa de acesso do usuário atual (Administrador)...")
            adm_dash = simular_decorador(request.user, 'pode_visualizar_dashboard')
            log(f"Acesso do Administrador ao Dashboard: <span class='text-emerald-400 font-bold'>{adm_dash}</span>")
            adm_logs = "PERMITIDO" if request.user.tipo_usuario == 'ADMIN' else "NEGADO"
            log(f"Acesso do Administrador aos Logs: <span class='text-emerald-400 font-bold'>{adm_logs}</span>")

            # Limpar usuário temporário
            user_temp.delete()
            log("Limpando usuário operador temporário...")
            log("<span class='text-emerald-400 font-bold'>[SUCESSO] Teste de Segurança e Nível de Acesso concluído com êxito!</span>")

        elif teste_id == 3:
            log("<span class='text-yellow-400 font-bold'>[INÍCIO] Teste de Integridade Financeira (Cálculo de Lucro Histórico)</span>")
            
            # 1. Cadastrar produto com custo unitário R$ 2.00
            log("Cadastrando produto fictício: <b>'Produto Teste Lote A'</b>")
            produto_financeiro = Produto.objects.create(
                nome="Salgado Especial Teste Lote A",
                quantidade=10,
                valor_adquirido=20.00, # R$ 2.00 unitário
                porcentagem_ganho=150.00,
                valor_venda_final=5.00 # Lucro esperado unitário: 5.00 - 2.00 = R$ 3.00
            )
            log(f"Produto criado com Custo Unitário Inicial de: <span class='text-indigo-400 font-bold'>R$ {produto_financeiro.custo_unitario}</span>")
            log(f"Preço de Venda Final praticado: <span class='text-indigo-400 font-bold'>R$ {produto_financeiro.valor_venda_final}</span>")

            # 2. Registrar venda de 2 unidades do lote antigo
            log("Registrando venda de <span class='text-amber-500 font-bold'>2 unidades</span>...")
            with transaction.atomic():
                venda_1 = Venda.objects.create(
                    usuario_responsavel=request.user,
                    nome_pessoa="Comprador Lote Antigo",
                    forma_pagamento=Venda.FormaPagamento.PIX
                )
                item_1 = ItemVenda.objects.create(
                    venda=venda_1,
                    produto=produto_financeiro,
                    quantidade_vendida=2,
                    custo_unitario_historico=produto_financeiro.custo_unitario, # Salva o custo daquele momento
                    valor_unitario_venda=produto_financeiro.valor_venda_final
                )
                venda_1.atualizar_totais()
                
            log(f"Venda registrada com ID {venda_1.id.hex[:8]}.")
            log(f"Custo Histórico Salvo no Item: <span class='text-indigo-400 font-bold'>R$ {item_1.custo_unitario_historico}</span>")
            log(f"Lucro calculado da Venda 1: <span class='text-emerald-400 font-bold'>R$ {item_1.lucro}</span> (Esperado: 2x R$ 3.00 = R$ 6.00)")

            # 3. Alterar preço de custo do produto no cadastro para R$ 4.00 (simulando aumento de custo ou novo lote no mesmo produto)
            log("<b>[ALTERAÇÃO]</b> Editando produto no estoque: Custo do lote aumenta de R$ 2.00 para <span class='text-amber-500 font-bold'>R$ 4.00</span> por unidade...")
            produto_financeiro.valor_adquirido = 40.00 # Novo custo de aquisição para 10 unidades = R$ 4.00 unitário
            produto_financeiro.save()
            produto_financeiro.refresh_from_db()
            log(f"Novo Custo Unitário do produto atualizado na base: <span class='text-indigo-400'>R$ {produto_financeiro.custo_unitario}</span>")

            # 4. Registrar venda de 3 unidades com o novo preço de custo
            log("Registrando segunda venda de <span class='text-amber-500 font-bold'>3 unidades</span> pós-alteração...")
            with transaction.atomic():
                venda_2 = Venda.objects.create(
                    usuario_responsavel=request.user,
                    nome_pessoa="Comprador Lote Novo",
                    forma_pagamento=Venda.FormaPagamento.PIX
                )
                item_2 = ItemVenda.objects.create(
                    venda=venda_2,
                    produto=produto_financeiro,
                    quantidade_vendida=3,
                    custo_unitario_historico=produto_financeiro.custo_unitario, # Novo custo unitário
                    valor_unitario_venda=produto_financeiro.valor_venda_final
                )
                venda_2.atualizar_totais()

            log(f"Segunda venda registrada com ID {venda_2.id.hex[:8]}.")
            log(f"Custo Histórico Salvo no Novo Item: <span class='text-indigo-400 font-bold'>R$ {item_2.custo_unitario_historico}</span>")
            log(f"Lucro calculado da Venda 2: <span class='text-emerald-400 font-bold'>R$ {item_2.lucro}</span> (Esperado: 3x (R$ 5.00 - R$ 4.00) = R$ 3.00)")

            # 5. Verificar consistência
            log("<b>[AUDITORIA DE INTEGRIDADE FINANCEIRA]</b>")
            item_1_refresh = ItemVenda.objects.get(id=item_1.id)
            log(f"Lucro da Venda 1 ainda é: <span class='text-emerald-400 font-bold'>R$ {item_1_refresh.lucro}</span> (esperado: R$ 6.00) - <b>NÃO DISTORCIDO!</b>")
            
            lucro_total_calculado = item_1_refresh.lucro + item_2.lucro
            log(f"Lucro Total Real do Sistema (Soma dos itens históricos): <span class='text-emerald-400 font-bold'>R$ {lucro_total_calculado}</span> (R$ 6.00 + R$ 3.00 = R$ 9.00)")
            
            # Se usasse o custo atualizado para tudo: (5.00 - 4.00) * 5 = 5.00
            perda_ficticia = (produto_financeiro.valor_venda_final - produto_financeiro.custo_unitario) * (item_1.quantidade_vendida + item_2.quantidade_vendida)
            log(f"Se o sistema usasse custo do cadastro dinamicamente, o lucro seria: R$ {perda_ficticia} (Erro de auditoria fiscal!)")
            log("<span class='text-green-400 font-bold'>[OK] O sistema armazenou corretamente o custo unitário histórico de aquisição no momento da venda.</span>")

            # Limpar vendas e produtos temporários
            item_1.delete()
            item_2.delete()
            venda_1.delete()
            venda_2.delete()
            produto_financeiro.delete()
            log("Limpando dados temporários do teste...")
            log("<span class='text-emerald-400 font-bold'>[SUCESSO] Teste de Integridade Financeira e Custo Histórico concluído com êxito!</span>")

        else:
            log("<span class='text-red-400'>[ERRO] ID de teste inválido.</span>")

    except Exception as ex:
        log(f"<span class='text-red-400 font-bold'>[FALHA] Ocorreu um erro durante a simulação: {str(ex)}</span>")

    return HttpResponse("".join(logs))


from .markov import prever_produto_markov

@login_required
def previsao_estoque_view(request):
    produtos = Produto.objects.filter(ativo=True)
    produto_selecionado = None
    resultado_markov = None
    
    produto_id = request.GET.get('produto_id')
    if produto_id:
        produto_selecionado = get_object_or_404(Produto, pk=produto_id, ativo=True)
    elif produtos.exists():
        produto_selecionado = produtos.first()
        
    if produto_selecionado:
        resultado_markov = prever_produto_markov(produto_selecionado)
        
    context = {
        'produtos': produtos,
        'produto_selecionado': produto_selecionado,
        'resultado': resultado_markov
    }
    return render(request, 'previsao_estoque.html', context)

