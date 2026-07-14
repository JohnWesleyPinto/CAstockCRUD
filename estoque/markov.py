import datetime
import random
from django.utils import timezone
from django.db.models import Sum
from estoque.models import Produto, Venda, ItemVenda

def obter_dados_historicos(produto, dias=30):
    """
    Retorna a série temporal de vendas diárias nos últimos N dias
    e a média de unidades vendidas em cada estado de demanda.
    """
    hoje = timezone.now().date()
    datas = [hoje - datetime.timedelta(days=i) for i in range(dias - 1, -1, -1)]
    
    # Dicionário de data -> quantidade vendida
    vendas_diarias = {d: 0 for d in datas}
    
    itens = ItemVenda.objects.filter(
        produto=produto,
        venda__data_venda__date__gte=datas[0],
        venda__data_venda__date__lte=datas[-1]
    ).values('venda__data_venda__date').annotate(total_qtd=Sum('quantidade_vendida'))
    
    for item in itens:
        dt = item['venda__data_venda__date']
        if dt in vendas_diarias:
            vendas_diarias[dt] = item['total_qtd']
            
    serie = [vendas_diarias[d] for d in datas]
    
    # Classifica e calcula médias por estado
    # Estados: 0 (Nenhuma: 0), 1 (Baixa: 1-2), 2 (Alta: 3+)
    valores_estado = {0: [], 1: [], 2: []}
    for qtd in serie:
        if qtd == 0:
            valores_estado[0].append(0)
        elif qtd <= 2:
            valores_estado[1].append(qtd)
        else:
            valores_estado[2].append(qtd)
            
    # Médias reais por estado para simulação
    medias_estado = {
        0: 0.0,
        1: sum(valores_estado[1]) / len(valores_estado[1]) if valores_estado[1] else 1.5,
        2: sum(valores_estado[2]) / len(valores_estado[2]) if valores_estado[2] else 4.0
    }
    
    return serie, medias_estado

def calcular_matriz_transicao(serie):
    """
    Calcula a Matriz de Transição de Probabilidade (TPM) 3x3
    a partir da série histórica de vendas diárias.
    """
    # Mapeia quantidades para estados (0, 1, 2)
    def obter_estado(qtd):
        if qtd == 0:
            return 0
        elif qtd <= 2:
            return 1
        return 2

    estados = [obter_estado(q) for q in serie]
    
    # Inicializa contagens de transição usando Laplace Smoothing (alpha = 0.5)
    # Isso evita probabilidades de 100% ou 0% artificiais devido à falta de dados históricos (zero-frequency problem)
    alpha = 0.5
    counts = [[alpha] * 3 for _ in range(3)]
    for t in range(len(estados) - 1):
        i = estados[t]
        j = estados[t+1]
        counts[i][j] += 1
        
    # Normaliza as linhas para obter as probabilidades
    tpm = [[0.0] * 3 for _ in range(3)]
    for i in range(3):
        row_sum = sum(counts[i])
        tpm[i] = [counts[i][j] / row_sum for j in range(3)]
            
    return tpm, estados[-1] if estados else 0

def rodar_simulacao_monte_carlo(estoque_inicial, tpm, estado_inicial, medias_estado, dias=7, simulacoes=1000):
    """
    Roda simulações de Monte Carlo baseadas na Cadeia de Markov para projetar
    o declínio diário do estoque e a probabilidade de ruptura (estoque = 0).
    """
    historicos_estoque = [[] for _ in range(dias + 1)]
    historicos_estoque[0] = [estoque_inicial] * simulacoes
    rupturas_no_dia = [0] * (dias + 1)
    
    for _ in range(simulacoes):
        estoque_atual = estoque_inicial
        estado_atual = estado_inicial
        
        for d in range(1, dias + 1):
            # Escolhe o próximo estado baseado na linha correspondente da TPM
            probs = tpm[estado_atual]
            rand = random.random()
            if rand < probs[0]:
                proximo_estado = 0
            elif rand < probs[0] + probs[1]:
                proximo_estado = 1
            else:
                proximo_estado = 2
                
            # Determina a quantidade vendida baseada no estado sorteado
            media = medias_estado[proximo_estado]
            if proximo_estado == 0:
                venda_sorteada = 0
            else:
                # Usa uma distribuição de Poisson aproximada para vendas
                venda_sorteada = max(0, int(random.gauss(media, media * 0.3) + 0.5))
                
            estoque_atual = max(0, estoque_atual - venda_sorteada)
            historicos_estoque[d].append(estoque_atual)
            estado_atual = proximo_estado

    # Calcula médias projetadas e probabilidades de ruptura
    projecao_estoque = []
    probabilidade_ruptura = []
    
    for d in range(dias + 1):
        media_dia = sum(historicos_estoque[d]) / simulacoes
        projecao_estoque.append(round(media_dia, 1))
        
        casos_ruptura = sum(1 for est in historicos_estoque[d] if est <= 0)
        probabilidade_ruptura.append(round((casos_ruptura / simulacoes) * 100, 1))
        
    return projecao_estoque, probabilidade_ruptura

def prever_produto_markov(produto, dias_projecao=7):
    """
    Executa a análise completa de Markov para um produto específico.
    """
    serie, medias_estado = obter_dados_historicos(produto)
    tpm, estado_atual = calcular_matriz_transicao(serie)
    
    projecao, prob_ruptura = rodar_simulacao_monte_carlo(
        estoque_inicial=produto.quantidade,
        tpm=tpm,
        estado_inicial=estado_atual,
        medias_estado=medias_estado,
        dias=dias_projecao
    )
    
    # Determina o dia estimado de ruptura
    dia_ruptura = None
    for d, est in enumerate(projecao):
        if est <= 0:
            dia_ruptura = d
            break
            
    # Calcula a média real de vendas diárias históricas
    demanda_media_diaria = sum(serie) / len(serie) if serie else 0.0

    # Pré-calcula matriz de probabilidade em percentual para o HTML
    tpm_percent = [[round(val * 100, 1) for val in row] for row in tpm]

    # Recomendação de reabastecimento
    sugestao_compra = 0
    if dia_ruptura is not None or prob_ruptura[-1] > 50:
        # Sugere lote para cobrir 14 dias de demanda média
        sugestao_compra = int(demanda_media_diaria * 14) - produto.quantidade
        sugestao_compra = max(10, (sugestao_compra // 5 + 1) * 5) # Arredonda para múltiplo de 5
        
    return {
        "produto_nome": produto.nome,
        "estoque_atual": produto.quantidade,
        "serie_historica": serie,
        "tpm": tpm,
        "tpm_percent": tpm_percent,
        "medias_estado": medias_estado,
        "demanda_media_diaria": round(demanda_media_diaria, 2),
        "projecao_estoque": projecao,
        "probabilidade_ruptura": prob_ruptura,
        "dia_estimado_ruptura": dia_ruptura,
        "sugestao_compra": sugestao_compra
    }
