# src/routes/chat.py
from flask import Blueprint, request, jsonify, session
import requests
from database.connection import SessionLocal
from models.nota_fiscal import NotaFiscal, ItemNota  # ItemNota pra detalhes
from models.usuario import Usuario  # Pra regime

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
        # Query: Últimas 5 notas do usuário (emitente ou destinatário)
        notas = db.query(NotaFiscal).filter(
            (NotaFiscal.cnpj_emitente == cnpj) | (NotaFiscal.cnpj_destinatario == cnpj)
        ).order_by(NotaFiscal.data_emissao.desc()).limit(5).all()

        # Query: Dados do usuário (regime tributário)
        usuario = db.query(Usuario).filter_by(cnpj=cnpj).first()
        regime = usuario.regime_tributario if usuario else "desconhecido"

        # Constrói contexto resumido com itens detalhados
        contexto = f"Regime tributário da empresa: {regime}. Use isso pra calcular impostos (ex: Simples Nacional anexa alíquotas por atividade/produto).\n"
        if not notas:
            contexto += "Nenhuma nota fiscal carregada ainda. Carregue via dashboard pra análise."
        else:
            contexto += "Suas últimas notas fiscais (com itens/produtos resumidos):\n"
            for nota in notas:
                itens_resumo = []
                # Query itens da nota (FK nota_id)
                itens = db.query(ItemNota).filter_by(nota_id=nota.id).limit(5).all()
                print(f"DEBUG: Nota {nota.id} tem {len(itens)} itens encontrados.")  # Debug
                if itens:
                    for item in itens:
                        # CORRIGIDO: Converte strings pra float antes de formatar :.2f
                        val_unit = float(getattr(item, 'valor_unitario', 0) or 0)
                        val_total = float(getattr(item, 'valor_total', 0) or 0)
                        qtd = float(getattr(item, 'quantidade', 0) or 0)
                        itens_resumo.append(
                            f"{item.descricao_produto or 'N/A'} (qtd: {qtd}, val unit: R${val_unit:.2f}, "
                            f"total: R${val_total:.2f}, NCM: {item.ncm or 'N/A'}, CFOP: {item.cfop or 'N/A'}, CST IPI: {item.cst_ipi or 'N/A'})"
                        )
                    itens_str = "; ".join(itens_resumo)
                else:
                    itens_str = "Sem itens detalhados nesta nota (verifique upload do XML)."
                contexto += f"- Nota {nota.numero} ({nota.data_emissao}): Valor total R${nota.valor_total_nota or 0}, Natureza: {nota.natureza_operacao or 'N/A'}. Itens: {itens_str}.\n"

        db.close()
        print(f"DEBUG CONTEXTO GERADO (primeiros 500 chars): {contexto[:500]}...")  # Debug

        try:
            # Detectar tipo de modelo pela chave
            if api_key.startswith("AIza"):  # Gemini
                resposta = chamar_gemini(pergunta, api_key, contexto)
            elif api_key.startswith("gsk_"):  # Grok
                resposta = chamar_grok(pergunta, api_key, contexto)
            else:
                return jsonify({"erro": "Chave de API inválida ou não reconhecida."}), 400

            return jsonify({"resposta": resposta}), 200

        except Exception as e:
            print(f"DEBUG ERRO IA: {e}")  # Debug
            return jsonify({"erro": f"Erro ao processar IA: {str(e)}"}), 500

    except Exception as e:
        print(f"DEBUG ERRO GERAL: {e}")  # Debug
        if 'db' in locals():
            db.close()
        return jsonify({"erro": f"Erro ao acessar dados: {str(e)}"}), 500


# 🔹 Função auxiliar - Gemini API (usando SDK oficial)
def chamar_gemini(pergunta, api_key, contexto):
    """
    Envia pergunta à API Gemini com contexto das notas
    """
    from services.gemini_service import chamar_gemini as gemini_call  # Importa o serviço que você mandou
    prompt = f"Você é um assistente fiscal especialista. Use APENAS o contexto abaixo para responder à pergunta do usuário de forma precisa, concisa e útil. Foque em produtos, impostos devidos, economia (ex: deduções por regime), produto mais vendido (some qtds/valores cross-notas), etc. Responda em português.\n\nContexto das notas fiscais: {contexto}\n\nPergunta: {pergunta}\n\nResposta:"
    return gemini_call(prompt, api_key)


# 🔹 Função auxiliar - Grok API
def chamar_grok(pergunta, api_key, contexto):
    """
    Envia pergunta à API Grok com contexto no system message
    """
    url = "https://api.x.ai/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    system_prompt = f"Você é um assistente fiscal especialista em notas fiscais, CNPJ, IR e impostos. Use APENAS o contexto abaixo para responder à pergunta do usuário de forma precisa, concisa e útil. Foque em produtos, impostos devidos, economia (ex: deduções por regime), produto mais vendido (some qtds/valores cross-notas), etc. Responda em português.\n\nContexto das notas fiscais: {contexto}"
    body = {
        "model": "grok-beta",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": pergunta}
        ]
    }

    response = requests.post(url, headers=headers, json=body)
    if response.status_code == 200:
        data = response.json()
        try:
            return data["choices"][0]["message"]["content"]
        except Exception:
            return "A IA respondeu, mas não foi possível interpretar o retorno."
    else:
        return f"Erro Grok: {response.status_code} → {response.text}"