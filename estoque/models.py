import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models.signals import post_save
from django.dispatch import receiver

# 1. Custom User Model
class Usuario(AbstractUser):
    TIPO_USUARIO_CHOICES = (
        ('ADMIN', 'Administrador'),
        ('MEMBRO', 'Membro Operacional'),
    )
    
    tipo_usuario = models.CharField(
        max_length=10,
        choices=TIPO_USUARIO_CHOICES,
        default='MEMBRO',
        help_text="Define o nível de acesso e perfil do usuário"
    )
    foto = models.FileField(
        upload_to='perfil/',
        null=True,
        blank=True,
        help_text="Foto de perfil do usuário"
    )

    def __str__(self):
        return f"{self.username} ({self.get_tipo_usuario_display()})"


# 2. Dynamic Permissions Model
class MembroPermissao(models.Model):
    usuario = models.OneToOneField(
        Usuario,
        on_delete=models.CASCADE,
        related_name='permissoes'
    )
    pode_cadastrar_produto = models.BooleanField(default=False)
    pode_editar_produto = models.BooleanField(default=False)
    pode_excluir_produto = models.BooleanField(default=False)
    pode_visualizar_dashboard = models.BooleanField(default=False)
    pode_cadastrar_venda = models.BooleanField(default=False)
    pode_alterar_porcentagem_lucro = models.BooleanField(default=False)
    pode_gerenciar_membros = models.BooleanField(default=False)

    def __str__(self):
        return f"Permissões de {self.usuario.username}"


# 3. System Configuration Singleton Model
class ConfiguracaoSistema(models.Model):
    margem_lucro_padrao = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=30.00,
        help_text="Margem de lucro global sugerida para novos produtos (%)"
    )
    gemini_api_key = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Chave de API do Gemini para habilitar o chatbot de IA"
    )

    def save(self, *args, **kwargs):
        self.pk = 1  # Força a ser sempre o mesmo registro (Singleton)
        super().save(*args, **kwargs)

    @classmethod
    def get_config(cls):
        config, created = cls.objects.get_or_create(pk=1)
        return config

    def __str__(self):
        return f"Configurações Globais (Margem padrão: {self.margem_lucro_padrao}%)"


# 4. Product Model
class Produto(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=255)
    quantidade = models.IntegerField(default=0, help_text="Quantidade total de unidades no estoque")
    data_compra = models.DateTimeField(null=True, blank=True)
    valor_adquirido = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Valor total de custo gasto na aquisição desse lote"
    )
    porcentagem_ganho = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Porcentagem de ganho desejada sobre o custo unitário (%)"
    )
    valor_venda_sugerido = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text="Valor de venda sugerido baseado na porcentagem de ganho"
    )
    valor_venda_final = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text="Valor efetivo de venda praticado"
    )
    eh_caixa = models.BooleanField(
        default=False,
        help_text="Indica se o produto foi comprado fechado em caixa de múltiplas unidades"
    )
    quantidade_por_caixa = models.IntegerField(
        default=1,
        null=True,
        blank=True,
        help_text="Se comprado em caixa, quantas unidades físicas vem dentro dela"
    )
    custo_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text="Custo de aquisição unitário calculado"
    )
    ativo = models.BooleanField(
        default=True,
        help_text="Soft Delete: Define se o produto está ativo no sistema"
    )

    def clean(self):
        # 1. Calcular custo unitário
        if self.pk:
            try:
                original = self.__class__.objects.get(pk=self.pk)
                if original.valor_adquirido == self.valor_adquirido and original.custo_unitario and original.custo_unitario > 0:
                    self.custo_unitario = original.custo_unitario
                else:
                    if self.eh_caixa:
                        qtd_por_cx = self.quantidade_por_caixa or 1
                        if qtd_por_cx < 1:
                            qtd_por_cx = 1
                        self.custo_unitario = self.valor_adquirido / qtd_por_cx
                    else:
                        if self.quantidade > 0:
                            self.custo_unitario = self.valor_adquirido / self.quantidade
                        else:
                            self.custo_unitario = self.valor_adquirido
            except self.__class__.DoesNotExist:
                # Objeto com PK setado mas que ainda não existe no banco (ex: UUID padrão no create)
                if self.eh_caixa:
                    qtd_por_cx = self.quantidade_por_caixa or 1
                    if qtd_por_cx < 1:
                        qtd_por_cx = 1
                    self.custo_unitario = self.valor_adquirido / qtd_por_cx
                else:
                    if self.quantidade > 0:
                        self.custo_unitario = self.valor_adquirido / self.quantidade
                    else:
                        self.custo_unitario = self.valor_adquirido
        else:
            if self.eh_caixa:
                qtd_por_cx = self.quantidade_por_caixa or 1
                if qtd_por_cx < 1:
                    qtd_por_cx = 1
                self.custo_unitario = self.valor_adquirido / qtd_por_cx
            else:
                if self.quantidade > 0:
                    self.custo_unitario = self.valor_adquirido / self.quantidade
                else:
                    self.custo_unitario = self.valor_adquirido
        
        # 2. Calcular preço de venda sugerido
        # Sugerido = Custo Unitário * (1 + Porcentagem de Ganho / 100)
        self.valor_venda_sugerido = self.custo_unitario * (1 + (self.porcentagem_ganho / 100))

    def save(self, *args, **kwargs):
        self.clean()
        # Se o valor final de venda não for fornecido, assume o valor sugerido
        if not self.valor_venda_final or self.valor_venda_final == 0:
            self.valor_venda_final = self.valor_venda_sugerido
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nome} ({self.quantidade} un)"


# 5. Sale (Header) Model
class Venda(models.Model):
    class FormaPagamento(models.IntegerChoices):
        CAIXINHA = 1, 'Caixinha'
        PIX = 2, 'Pix'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario_responsavel = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='vendas_realizadas'
    )
    nome_pessoa = models.CharField(
        max_length=255,
        help_text="Identificação de quem comprou ou retirou"
    )
    forma_pagamento = models.IntegerField(
        choices=FormaPagamento.choices,
        default=FormaPagamento.PIX
    )
    valor_total_venda = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00
    )
    lucro_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00
    )
    data_venda = models.DateTimeField(auto_now_add=True)

    def atualizar_totais(self):
        # Recalcula totais com base nos itens cadastrados
        itens = self.itens.all()
        self.valor_total_venda = sum(item.quantidade_vendida * item.valor_unitario_venda for item in itens)
        self.lucro_total = sum(item.lucro for item in itens)
        self.save()

    def __str__(self):
        return f"Venda {str(self.id)[:8]} - {self.nome_pessoa} (R$ {self.valor_total_venda})"


# 6. Item Sale Model (N-N intermediary table)
class ItemVenda(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    venda = models.ForeignKey(
        Venda,
        on_delete=models.CASCADE,
        related_name='itens'
    )
    produto = models.ForeignKey(
        Produto,
        on_delete=models.PROTECT,
        related_name='vendas_itens'
    )
    quantidade_vendida = models.IntegerField()
    custo_unitario_historico = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Custo unitário do produto na hora da venda para garantir integridade do lucro histórico"
    )
    valor_unitario_venda = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Preço final unitário de venda praticado neste item"
    )
    lucro = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text="Lucro obtido nessa venda (Valor Venda - Custo Histórico) * Qtd"
    )

    def clean(self):
        # Lucro = (Venda Unitária - Custo Histórico) * Quantidade
        from decimal import Decimal
        venda_unitaria = Decimal(str(self.valor_unitario_venda))
        custo_historico = Decimal(str(self.custo_unitario_historico))
        self.lucro = (venda_unitaria - custo_historico) * self.quantidade_vendida

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.quantidade_vendida}x {self.produto.nome} na Venda {str(self.venda.id)[:8]}"


# 7. System Audit Log Model
class LogSistema(models.Model):
    class NivelLog(models.TextChoices):
        INFO = 'Information', 'Information'
        WARN = 'Warning', 'Warning'
        ERR = 'Error', 'Error'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    acao = models.CharField(max_length=100)
    descricao = models.TextField()
    nivel = models.CharField(
        max_length=15,
        choices=NivelLog.choices,
        default=NivelLog.INFO
    )
    data_hora = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-data_hora']

    def __str__(self):
        user_str = self.usuario.username if self.usuario else "Sistema"
        return f"[{self.nivel}] {self.data_hora.strftime('%d/%m/%Y %H:%M:%S')} - {user_str}: {self.acao}"


# Utility function to easily create logs
def registrar_log(usuario, acao, descricao, nivel=LogSistema.NivelLog.INFO):
    return LogSistema.objects.create(
        usuario=usuario,
        acao=acao,
        descricao=descricao,
        nivel=nivel
    )


# 8. Signals for automatically creating permissions
@receiver(post_save, sender=Usuario)
def gerenciar_permissoes_usuario(sender, instance, created, **kwargs):
    if created:
        # Se for superusuario ou admin, ganha permissões por padrão
        eh_admin = instance.is_superuser or instance.tipo_usuario == 'ADMIN'
        MembroPermissao.objects.create(
            usuario=instance,
            pode_cadastrar_produto=eh_admin,
            pode_editar_produto=eh_admin,
            pode_excluir_produto=eh_admin,
            pode_visualizar_dashboard=eh_admin,
            pode_cadastrar_venda=True,  # Membros por padrão podem registrar vendas (operacional)
            pode_alterar_porcentagem_lucro=eh_admin,
            pode_gerenciar_membros=eh_admin
        )
