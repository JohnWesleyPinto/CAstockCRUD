import random
import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from estoque.models import Produto, Venda, ItemVenda, LogSistema, Usuario

class Command(BaseCommand):
    help = "Popula o banco com compras (restock logs) e vendas simuladas nos últimos 30 dias com comportamentos contrastantes"

    def handle(self, *args, **options):
        self.stdout.write("Iniciando o seeding de dados históricos...")

        # 1. Garante que temos um usuário administrador ou padrão para associar
        admin = Usuario.objects.filter(tipo_usuario='ADMIN').first() or Usuario.objects.first()
        if not admin:
            self.stdout.write(self.style.ERROR("Nenhum usuário cadastrado no sistema! Cadastre um primeiro."))
            return

        # 2. Garante a criação dos produtos com padrões de vendas contrastantes
        p_alta, _ = Produto.objects.get_or_create(
            nome="Água Mineral 500ml",
            defaults={
                "quantidade": 150,
                "valor_adquirido": 150.00,
                "porcentagem_ganho": 100.00,
                "valor_venda_final": 2.00,
                "data_compra": timezone.now(),
                "ativo": True
            }
        )
        p_baixa, _ = Produto.objects.get_or_create(
            nome="Energético Red Bull",
            defaults={
                "quantidade": 15,
                "valor_adquirido": 90.00,
                "porcentagem_ganho": 50.00,
                "valor_venda_final": 9.00,
                "data_compra": timezone.now(),
                "ativo": True
            }
        )

        produtos = Produto.objects.filter(ativo=True)

        # 3. Registra logs de compra (Reabastecimento/Restock)
        self.stdout.write("Registrando logs de compras de lotes históricos...")
        for p in produtos:
            # Simula compras de abastecimento nas últimas semanas
            for semanas_atras in [3, 2, 1]:
                data_compra = timezone.now() - datetime.timedelta(weeks=semanas_atras, days=random.randint(0, 4))
                qtd_comprada = random.randint(30, 80)
                valor_compra = float(p.valor_venda_final) * 0.7 * qtd_comprada

                log = LogSistema.objects.create(
                    usuario=admin,
                    acao="Compra de Lote",
                    descricao=f"Compra/Entrada de {qtd_comprada} un do produto '{p.nome}' a R$ {valor_compra:.2f}/lote",
                    nivel=LogSistema.NivelLog.INFO
                )
                LogSistema.objects.filter(pk=log.pk).update(data_hora=data_compra)

        # 4. Simula vendas nos últimos 30 dias com contraste de demanda
        self.stdout.write("Simulando 30 dias de vendas diárias para Cadeia de Markov...")
        nomes_compradores = ["João Silva", "Maria Santos", "Pedro Souza", "Lucas Lima", "Ana Oliveira", "Juliana Costa", "Carlos Barbosa", "Fernanda Cruz"]
        
        hoje = timezone.now()
        vendas_criadas = 0

        for dia in range(30, 0, -1):
            data_venda = hoje - datetime.timedelta(days=dia, hours=random.randint(8, 18), minutes=random.randint(0, 59))
            
            # Cria a venda do dia
            v = Venda.objects.create(
                usuario_responsavel=admin,
                nome_pessoa=random.choice(nomes_compradores),
                forma_pagamento=random.choice([Venda.FormaPagamento.PIX, Venda.FormaPagamento.CAIXINHA]),
                valor_total_venda=0.0,
                lucro_total=0.0
            )
            
            # A) Sempre vende Água Mineral (venda alta: 3 a 5 unidades por dia)
            qtd_agua = random.randint(3, 5)
            ItemVenda.objects.create(
                venda=v,
                produto=p_alta,
                quantidade_vendida=qtd_agua,
                custo_unitario_historico=1.00,
                valor_unitario_venda=p_alta.valor_venda_final
            )
            
            # B) Vende Red Bull raramente (apenas a cada 6 dias, 1 unidade)
            if dia % 6 == 0:
                ItemVenda.objects.create(
                    venda=v,
                    produto=p_baixa,
                    quantidade_vendida=1,
                    custo_unitario_historico=6.00,
                    valor_unitario_venda=p_baixa.valor_venda_final
                )
                
            # C) Seleciona de 1 a 2 outros produtos para compor a venda
            outros_produtos = [p for p in produtos if p.id not in [p_alta.id, p_baixa.id]]
            if outros_produtos:
                produtos_venda = random.sample(outros_produtos, k=random.randint(1, min(2, len(outros_produtos))))
                for prod in produtos_venda:
                    qtd_vendida = random.randint(1, 2)
                    custo_historico = prod.valor_adquirido / max(prod.quantidade, 1)
                    ItemVenda.objects.create(
                        venda=v,
                        produto=prod,
                        quantidade_vendida=qtd_vendida,
                        custo_unitario_historico=custo_historico,
                        valor_unitario_venda=prod.valor_venda_final
                    )
            
            # Recalcula totais
            v.atualizar_totais()
            
            # Sobrescreve a data_venda para o passado usando update
            Venda.objects.filter(pk=v.pk).update(data_venda=data_venda)
            vendas_criadas += 1

        self.stdout.write(self.style.SUCCESS(f"Seeding concluído! {vendas_criadas} vendas históricas e logs de reabastecimento registrados com sucesso."))
