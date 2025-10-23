# src/routes/chat.py
from flask import Blueprint, request, jsonify, session
import requests
import time  # Para retry
from database.connection import SessionLocal
from models.nota_fiscal import NotaFiscal, ItemNota  # ItemNota pra detalhes
from models.usuario import Usuario  # Pra regime
from services.gemini_service import chamar_gemini  # Mantenha para Grok se necessário, mas use processar_pergunta_chat para Gemini

chat_bp = Blueprint("chat_bp", __name__)

@chat_bp.route("/chat", methods=["POST"])
def chat_ia():
    """
    Endpoint de chat fiscal inteligente (Gemini ou Grok) com contexto das notas do usuário
    """
    data = request.get_json()
    pergunta = data.get("pergunta")
    api_key = data.get("apiKey")

    if not pergunta:
        return jsonify({"erro": "Pergunta não fornecida."}), 400
    if not api_key:
        return jsonify({"erro": "Chave da API não fornecida."}), 400

    # Verifica autenticação via sessão
    cnpj = session.get("cnpj")
    if not cnpj:
        return jsonify({"erro": "Não autorizado. Faça login."}), 401

    db = SessionLocal()
    try:
        # Detectar se pergunta é sobre saída/entrada para filtrar query
        is_saida = "saida" in pergunta.lower() or "saída" in pergunta.lower()
        is_entrada = "entrada" in pergunta.lower()

        filter_tipo = None
        if is_saida and not is_entrada:
            filter_tipo = 'Saída'
        elif is_entrada and not is_saida:
            filter_tipo = 'Entrada'

        # Query: Últimas 5 notas do usuário (emitente ou destinatário), filtrado se aplicável
        query = db.query(NotaFiscal).filter(
            (NotaFiscal.cnpj_emitente == cnpj) | (NotaFiscal.cnpj_destinatario == cnpj)
        )
        if filter_tipo:
            query = query.filter(NotaFiscal.tipo_operacao == filter_tipo)
        notas = query.order_by(NotaFiscal.data_emissao.desc()).limit(5).all()

        # Query: Dados do usuário (regime tributário + natureza_juridica)
        usuario = db.query(Usuario).filter_by(cnpj=cnpj).first()
        regime = usuario.regime_tributario if usuario else "desconhecido"
        natureza = usuario.natureza_juridica if usuario else "desconhecida"

        # Constrói contexto resumido com itens detalhados + impostos (mais conciso)
        contexto = f"Regime: {regime}, Natureza: {natureza}.\n"
        if not notas:
            contexto += "Nenhuma nota encontrada."
        else:
            contexto += "Notas:\n"
            for nota in notas:
                itens_resumo = []
                itens = db.query(ItemNota).filter_by(nota_id=nota.id).all()  # Removido limit para completude, mas mantém conciso
                print(f"DEBUG CHAT: Nota {nota.id} tem {len(itens)} itens encontrados.")  # Debug
                if itens:
                    for item in itens:
                        val_unit = float(getattr(item, 'valor_unitario', 0) or 0)
                        val_total = float(getattr(item, 'valor_total', 0) or 0)
                        qtd = float(getattr(item, 'quantidade', 0) or 0)
                        icms_item = float(getattr(item, 'icms_valor', 0) or 0)
                        ipi_item = float(getattr(item, 'ipi_valor', 0) or 0)
                        pis_item = float(getattr(item, 'pis_valor', 0) or 0)
                        cofins_item = float(getattr(item, 'cofins_valor', 0) or 0)
                        itens_resumo.append(
                            f"{item.descricao_produto or 'N/A'} (qtd:{qtd}, unit:R${val_unit:.2f}, total:R${val_total:.2f}, NCM:{item.ncm or 'N/A'}, CFOP:{item.cfop or 'N/A'}, CST IPI:{item.cst_ipi or 'N/A'}, ICMS:R${icms_item:.2f}, IPI:R${ipi_item:.2f}, PIS:R${pis_item:.2f}, COFINS:R${cofins_item:.2f})"
                        )
                    itens_str = "; ".join(itens_resumo)
                else:
                    itens_str = "Sem itens."
                contexto += f"- Nota {nota.numero} ({nota.data_emissao}): Total R${nota.valor_total_nota or 0}, Natureza: {nota.natureza_operacao or 'N/A'}, Tipo: {nota.tipo_operacao or 'N/A'}. Itens: {itens_str}.\n"

        db.close()
        print(f"DEBUG CONTEXTO: {contexto[:500]}...")  # Debug

        try:
            # Detectar tipo de modelo pela chave
            if api_key.startswith("AIza"):  # Gemini
                resposta = chamar_gemini_with_retry(pergunta, api_key, contexto, cnpj)
            elif api_key.startswith("gsk_"):  # Grok
                resposta = chamar_grok_with_retry(pergunta, api_key, contexto, cnpj)
            else:
                return jsonify({"erro": "Chave de API inválida."}), 400

            return jsonify({"resposta": resposta}), 200

        except Exception as e:
            print(f"DEBUG ERRO IA: {e}")
            return jsonify({"erro": f"Erro ao processar IA: {str(e)}"}), 500

    except Exception as e:
        print(f"DEBUG ERRO GERAL: {e}")
        if 'db' in locals():
            db.close()
        return jsonify({"erro": f"Erro ao acessar dados: {str(e)}"}), 500


# 🔹 Função auxiliar - Gemini com retry
def chamar_gemini_with_retry(pergunta, api_key, contexto, user_cnpj, max_retries=3):
    for attempt in range(max_retries):
        try:
            prompt = f"Assistente fiscal. Responda concisa e diretamente, sem texto extra ou sugestões a menos que pedidas. Use tabela só para breakdown se necessário. Foque na pergunta.\n\nClassifique saída/entrada por tipo_operacao ('Saída' se emitente={user_cnpj}, 'Entrada' se destinatário={user_cnpj}). Ignore natureza_operacao para classificação.\n\nAnalise itens por nota para impostos por produto (ex: icms_valor individual). Some impostos cross-itens/notas.\n\nContexto: {contexto}\n\nPergunta: {pergunta}\nResposta:"
            from services.gemini_service import chamar_gemini as gemini_call
            return gemini_call(prompt, api_key)
        except Exception as e:
            if "503" in str(e) and attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
            raise e


# 🔹 Função auxiliar - Grok com retry
def chamar_grok_with_retry(pergunta, api_key, contexto, user_cnpj, max_retries=3):
    url = "https://api.x.ai/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    system_prompt = f"Assistente fiscal. Responda concisa e diretamente, sem texto extra ou sugestões a menos que pedidas. Use tabela só para breakdown se necessário. Foque na pergunta.\n\nClassifique saída/entrada por tipo_operacao ('Saída' se emitente={user_cnpj}, 'Entrada' se destinatário={user_cnpj}). Ignore natureza_operacao para classificação.\n\nAnalise itens por nota para impostos por produto (ex: icms_valor individual). Some impostos cross-itens/notas.\n\nContexto: {contexto}"
    body = {
        "model": "grok-beta",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": pergunta}
        ]
    }

    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=body)
            if response.status_code == 200:
                data = response.json()
                try:
                    return data["choices"][0]["message"]["content"]
                except Exception:
                    return "Erro ao interpretar resposta."
            else:
                if response.status_code == 503 and attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                return f"Erro Grok: {response.status_code} → {response.text}"
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            return f"Erro ao chamar Grok: {str(e)}"