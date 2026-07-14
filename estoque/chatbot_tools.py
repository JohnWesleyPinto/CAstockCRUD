from django.db.models import Sum
from django.utils import timezone
from .models import Produto, Venda

def obter_estoque_critico(limite: int = 5) -> list:
    """
    Retorna a lista de produtos ativos com estoque baixo (menor que o limite especificado).
    Use esta função quando o usuário perguntar sobre produtos acabando, falta de estoque ou estoque crítico.
    """
    produtos = Produto.objects.filter(ativo=True, quantidade__lt=limite).values('nome', 'quantidade')
    return list(produtos)

def buscar_produto_por_nome(nome: str) -> list:
    """
    Busca produtos ativos no estoque pelo nome (busca insensível a maiúsculas/minúsculas).
    Use esta função para pesquisar as quantidades e preços de produtos específicos no estoque.
    """
    produtos = Produto.objects.filter(ativo=True, nome__icontains=nome).values('nome', 'quantidade', 'valor_venda_final')
    return [
        {
            "nome": p["nome"],
            "quantidade": p["quantidade"],
            "valor_venda_final": float(p["valor_venda_final"])
        }
        for p in produtos
    ]

def obter_faturamento_do_dia() -> dict:
    """
    Retorna o faturamento total das vendas realizadas no dia de hoje.
    Use esta função para responder a perguntas sobre vendas de hoje, faturamento diário ou total vendido hoje.
    """
    hoje = timezone.now().date()
    total = Venda.objects.filter(data_venda__date=hoje).aggregate(total=Sum('valor_total_venda'))['total']
    return {"faturamento_total_hoje": float(total or 0.0)}

def prever_estoque_futuro(produto_nome: str) -> dict:
    """
    Calcula previsões de estoque futuro e risco de esgotamento para um produto usando Cadeias de Markov.
    Use esta função sempre que o usuário perguntar sobre previsões de estoque, estimativa de quando um produto vai acabar,
    sugestão de quantidade para compra de lote ou análise de demanda futura.
    """
    produto = Produto.objects.filter(ativo=True, nome__icontains=produto_nome).first()
    if not produto:
        return {"erro": f"Produto '{produto_nome}' não encontrado no estoque."}
    
    from .markov import prever_produto_markov
    res = prever_produto_markov(produto)
    
    return {
        "produto": res["produto_nome"],
        "estoque_atual": res["estoque_atual"],
        "demanda_media_diaria": float(res["demanda_media_diaria"]),
        "probabilidade_ruptura_7_dias": float(res["probabilidade_ruptura"][-1]),
        "dia_estimado_ruptura": res["dia_estimado_ruptura"],
        "sugestao_compra": res["sugestao_compra"]
    }

# Lista de funções exportadas para o Gemini API
CHATBOT_TOOLS = [obter_estoque_critico, buscar_produto_por_nome, obter_faturamento_do_dia, prever_estoque_futuro]
