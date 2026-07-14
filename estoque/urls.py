from django.urls import path
from . import views, views_chatbot

urlpatterns = [
    # Chatbot Inteligente
    path('chatbot/send/', views_chatbot.chatbot_message_view, name='chatbot_send'),

    # Dashboard & Métricas
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('dashboard/dados/', views.dashboard_metrics, name='dashboard_metrics'),
    
    # Autenticação
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('cadastro/', views.cadastro_view, name='cadastro'),
    path('esqueceu-senha/', views.esqueceu_senha_view, name='esqueceu_senha'),
    
    # Perfil do Usuário
    path('perfil/', views.perfil_view, name='perfil'),
    path('perfil/senha/', views.alterar_senha_view, name='alterar_senha'),
    
    # Gestão de Membros
    path('membros/', views.membros_view, name='membros'),
    path('membros/permissao/<int:membro_id>/<str:permissao_campo>/', views.atualizar_permissao, name='atualizar_permissao'),
    
    # Gestão de Produtos
    path('produtos/', views.produtos_view, name='produtos'),
    path('produtos/adicionar/', views.adicionar_produto_view, name='adicionar_produto'),
    path('produtos/excluir/<uuid:produto_id>/', views.excluir_produto, name='excluir_produto'),
    
    # Fluxo de Vendas
    path('', views.vendas_view, name='vendas'),
    path('vendas/buscar-produto/', views.buscar_produto_venda, name='buscar_produto_venda'),
    path('vendas/registrar/', views.registrar_venda_action, name='registrar_venda'),
    
    # Configurações do Sistema
    path('configuracoes/', views.configuracoes_view, name='configuracoes'),
    
    # Previsão Inteligente (Markov)
    path('previsao-estoque/', views.previsao_estoque_view, name='previsao_estoque'),
    
    # Logs e Auditoria
    path('logs/', views.logs_view, name='logs'),

    # Demonstração e Testes
    path('testes/', views.testes_view, name='testes'),
    path('testes/resetar/', views.resetar_banco_view, name='resetar_banco'),
    path('testes/executar/<int:teste_id>/', views.executar_teste_view, name='executar_teste'),
]
