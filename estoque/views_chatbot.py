import os
import google.generativeai as genai
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.utils.html import escape
from decouple import config
from .models import ConfiguracaoSistema
from .chatbot_tools import CHATBOT_TOOLS, obter_estoque_critico, buscar_produto_por_nome, obter_faturamento_do_dia

@login_required
def chatbot_message_view(request):
    """
    Processa as mensagens enviadas ao chatbot.
    Se a chave GEMINI_API_KEY estiver configurada no banco de dados ou no arquivo .env,
    faz uso do modelo Gemini com Function Calling mapeando o banco do Django.
    Caso contrário, executa no Modo de Simulação Local direto no banco.
    """
    if request.method == 'POST':
        user_message = request.POST.get('message', '').strip()
        if not user_message:
            return HttpResponse("")

        db_config = ConfiguracaoSistema.get_config()
        api_key = db_config.gemini_api_key or config('GEMINI_API_KEY', default=os.environ.get('GEMINI_API_KEY', ''))
        bot_response = ""
        
        if api_key:
            try:
                genai.configure(api_key=api_key)
                
                # Inicializa o modelo com as ferramentas do banco
                model = genai.GenerativeModel(
                    model_name="gemini-3.5-flash",
                    tools=CHATBOT_TOOLS,
                    system_instruction=(
                        "Você é o CAStockBot, o assistente virtual inteligente do sistema CAStock. "
                        "Você tem acesso direto e em tempo real ao banco de dados do estoque através de ferramentas Python. "
                        "Sempre que o usuário perguntar sobre o nível de estoque atual, faturamento, buscar produtos "
                        "específicos ou relatórios de hoje, você DEVE acionar a ferramenta correspondente para "
                        "obter a informação correta do Django antes de responder. "
                        "Responda em português de forma extremamente curta, concisa e direta. Priorize a rapidez nas respostas."
                    )
                )
                
                chat = model.start_chat(enable_automatic_function_calling=True)
                response = chat.send_message(user_message)
                bot_response = response.text
            except Exception as e:
                bot_response = f"Erro na API do Gemini: {str(e)}\n\n(Verifique se a chave de API é válida ou use o modo local de simulação)."
        else:
            # Modo de Simulação Local (Sem chave API configurada)
            msg_lower = user_message.lower()
            if any(w in msg_lower for w in ["acabando", "estoque baixo", "baixo", "crítico", "critico"]):
                criticos = obter_estoque_critico()
                if criticos:
                    lista = ", ".join([f"**{p['nome']}** ({p['quantidade']} un)" for p in criticos])
                    bot_response = f"[Modo de Simulação] Os seguintes produtos estão com estoque crítico (abaixo de 5 unidades): {lista}."
                else:
                    bot_response = "[Modo de Simulação] Não há nenhum produto com estoque crítico no momento."
            elif any(w in msg_lower for w in ["faturamento", "faturou", "hoje", "vendeu hoje", "vendas hoje"]):
                faturamento = obter_faturamento_do_dia()
                bot_response = f"[Modo de Simulação] O faturamento total registrado no dia de hoje é de **R$ {faturamento['faturamento_total_hoje']:.2f}**."
            elif any(w in msg_lower for w in ["buscar", "pesquisar", "procurar", "estoque de", "tem o"]):
                # Tenta isolar o termo de busca de forma simples
                busca = ""
                for prefix in ["buscar", "pesquisar", "procurar", "estoque de", "tem o", "produto"]:
                    if prefix in msg_lower:
                        parts = msg_lower.split(prefix, 1)
                        if len(parts) > 1:
                            busca = parts[1].strip()
                            break
                if not busca:
                    # Fallback: pega a última palavra
                    busca = msg_lower.split()[-1]
                
                # Limpa pontuações
                busca = busca.replace("?", "").replace(".", "").strip()
                
                produtos = buscar_produto_por_nome(busca)
                if produtos:
                    lista = "\n- " + "\n- ".join([f"**{p['nome']}**: {p['quantidade']} un (Venda: R$ {p['valor_venda_final']:.2f})" for p in produtos])
                    bot_response = f"[Modo de Simulação] Encontrei os seguintes resultados para '{busca}':{lista}"
                else:
                    bot_response = f"[Modo de Simulação] Nenhum produto ativo foi encontrado com o nome '{busca}'."
            elif any(w in msg_lower for w in ["previsão", "previsao", "prever", "estimativa", "acabar"]):
                # Tenta isolar o termo de busca de forma simples
                busca = ""
                for prefix in ["previsão de", "previsao de", "prever", "estimativa de", "acabar", "estoque de"]:
                    if prefix in msg_lower:
                        parts = msg_lower.split(prefix, 1)
                        if len(parts) > 1:
                            busca = parts[1].strip()
                            break
                if not busca:
                    busca = msg_lower.split()[-1]
                busca = busca.replace("?", "").replace(".", "").strip()
                
                from .chatbot_tools import prever_estoque_futuro
                res = prever_estoque_futuro(busca)
                if "erro" in res:
                    bot_response = f"[Modo de Simulação] {res['erro']}"
                else:
                    ruptura_str = f"esgotará em **{res['dia_estimado_ruptura']} dias**" if res["dia_estimado_ruptura"] is not None else "**seguro (mais de 7 dias)**"
                    sugestao_str = f"+{res['sugestao_compra']} un" if res['sugestao_compra'] > 0 else 'Não necessita reabastecimento'
                    bot_response = (
                        f"[Modo de Simulação] Previsão de Markov para **{res['produto']}**:\n"
                        f"- Estoque atual: {res['estoque_atual']} un\n"
                        f"- Média diária de vendas: {res['demanda_media_diaria']} un/dia\n"
                        f"- Risco de ruptura em 7 dias: {res['probabilidade_ruptura_7_dias']}%\n"
                        f"- Tempo de vida estimado: {ruptura_str}\n"
                        f"- Compra sugerida: {sugestao_str}"
                    )
            else:
                bot_response = (
                    "[Modo de Simulação] Olá! Para utilizar a IA avançada do Gemini, configure a chave no menu de **Configurações do Sistema** (como Administrador) ou adicione `GEMINI_API_KEY` no seu `.env`.\n\n"
                    "Enquanto isso, posso responder a comandos simples mapeados ao banco:\n"
                    "- Pergunte sobre **'produtos acabando'** ou **'estoque baixo'**\n"
                    "- Pergunte sobre o **'faturamento de hoje'**\n"
                    "- Pergunte para **'buscar [nome do produto]'**\n"
                    "- Pergunte pela **'previsão de [nome do produto]'** para rodar Cadeia de Markov"
                )

        # Sanitiza e formata a resposta
        escaped_user = escape(user_message)
        escaped_bot = escape(bot_response).replace('\n', '<br>').replace('**', '<b>').replace('<b>', '<b>', 1) # Simple bold replacement
        # Let's clean up double stars formatting into strong HTML tags if there are any
        import re
        formatted_bot = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', escape(bot_response)).replace('\n', '<br>')

        response_html = f"""
        <div class="chat chat-start mb-3 animate-fade-in">
            <div class="chat-header opacity-50 text-xs mb-1">Assistente</div>
            <div class="chat-bubble chat-bubble-secondary text-sm shadow-md">{formatted_bot}</div>
        </div>
        """
        return HttpResponse(response_html)
