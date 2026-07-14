from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from .models import Usuario, Produto, Venda, ItemVenda, ConfiguracaoSistema

class CAStockTests(TestCase):
    def setUp(self):
        self.client = Client()
        # Criar admin
        self.admin = Usuario.objects.create_superuser(
            username='admin_test',
            email='admin@test.com',
            password='password123',
            tipo_usuario='ADMIN'
        )
        # Criar usuário operacional
        self.membro = Usuario.objects.create_user(
            username='membro_test',
            email='membro@test.com',
            password='password123',
            tipo_usuario='MEMBRO'
        )
        # Criar produto
        self.produto = Produto.objects.create(
            nome='Coca-Cola',
            quantidade=10,
            valor_adquirido=30.00,
            porcentagem_ganho=30.00,
            valor_venda_final=3.90
        )

    def test_vendas_view_publica(self):
        """Verifica se a tela de vendas é pública e retorna status 200."""
        response = self.client.get(reverse('vendas'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Coca-Cola')

    def test_configuracao_sistema_singleton(self):
        """Verifica se o modelo ConfiguracaoSistema funciona como Singleton e com valor padrão de 30%."""
        config = ConfiguracaoSistema.get_config()
        self.assertEqual(float(config.margem_lucro_padrao), 30.00)
        
        # Tenta criar outro e verifica se sobrescreve/mantém ID 1
        config.margem_lucro_padrao = 35.00
        config.save()
        
        config2 = ConfiguracaoSistema.get_config()
        self.assertEqual(config2.pk, 1)
        self.assertEqual(float(config2.margem_lucro_padrao), 35.00)

    def test_registrar_venda_anonima(self):
        """Verifica o registro de uma venda por operador anônimo (público) e a baixa no estoque."""
        url = reverse('registrar_venda')
        data = {
            'nome_pessoa': 'Comprador Anonimo',
            'forma_pagamento': '2', # Pix
            'produtos_ids[]': [str(self.produto.id)],
            'quantidades[]': ['2'],
            'valores_venda[]': ['3.90']
        }
        
        # Envia POST
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302) # Redirect de sucesso
        
        # Verifica se o estoque do produto foi deduzido
        self.produto.refresh_from_db()
        self.assertEqual(self.produto.quantidade, 8)
        
        # Verifica se a venda foi salva e o lucro total calculado
        venda = Venda.objects.last()
        self.assertIsNotNone(venda)
        self.assertEqual(venda.nome_pessoa, 'Comprador Anonimo')
        self.assertEqual(float(venda.valor_total_venda), 7.80)
        
        # Custo unitário de aquisição = 30.00 / 10 = 3.00. 
        # Venda unitária = 3.90. Lucro por item = 0.90. Total lucro = 1.80
        self.assertEqual(float(venda.lucro_total), 1.80)

    def test_acesso_configuracoes_admin_exclusivo(self):
        """Verifica se apenas administradores autenticados podem acessar a página de configurações."""
        url = reverse('configuracoes')
        
        # Deslogado: deve redirecionar para o login
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        
        # Logado como Membro: deve redirecionar para o dashboard com erro
        self.client.login(username='membro_test', password='password123')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        
        # Logado como Admin: deve acessar a página com sucesso (status 200)
        self.client.login(username='admin_test', password='password123')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_painel_testes_admin_exclusivo(self):
        """Verifica se apenas administradores podem acessar a página de testes."""
        url = reverse('testes')
        
        # Deslogado: redireciona
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        
        # Membro: redireciona
        self.client.login(username='membro_test', password='password123')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        
        # Admin: sucesso
        self.client.login(username='admin_test', password='password123')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_resetar_banco(self):
        """Verifica se a view de reset limpa as tabelas de dados mantendo os usuários."""
        # Garantir que há dados antes do reset
        self.assertTrue(Produto.objects.exists())
        
        self.client.login(username='admin_test', password='password123')
        url = reverse('resetar_banco')
        
        # Faz requisição POST para resetar
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302) # Redireciona de volta para testes
        
        # Verifica se limpou os produtos, mas manteve o usuário
        self.assertFalse(Produto.objects.exists())
        self.assertTrue(Usuario.objects.filter(username='admin_test').exists())

