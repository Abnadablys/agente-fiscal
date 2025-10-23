# src/services/gemini_service.py

import os
from google import genai
from database.connection import SessionLocal
from models.nota_fiscal import NotaFiscal
import json
import logging

logging.basicConfig(level=logging.DEBUG)

def chamar_gemini(prompt, api_key=None, modelo="gemini-2.5-flash"):
    """
    Usa o SDK oficial do Gemini (v2.5).
    Recebe o prompt e retorna o texto gerado.
    """
    try:
        if not api_key:
            return "❌ Nenhuma chave de API fornecida."

        # Configura a chave via ambiente
        os.environ["GEMINI_API_KEY"] = api_key

        # Cria cliente com a chave informada
        client = genai.Client(api_key=api_key)

        # Chamada para gerar conteúdo
        response = client.models.generate_content(
            model=modelo,
            contents=prompt
        )

        # Retorna o texto da resposta
        return response.text.strip()

    except Exception as e:
        return f"⚠️ Erro ao chamar Gemini: {e}"

def processar_pergunta_chat(pergunta, api_key, user_cnpj=""):
    """
    Constrói prompt para o chat, consultando DB e instruindo IA a usar tipo_operacao.
    Filtra notas relevantes se pergunta for sobre saída/entrada.
    """
    session = SessionLocal()
    try:
        # Consulta todas notas do usuário (assumindo filtro por user_cnpj se necessário; ajuste se tiver tabela Usuario)
        notas = session.query(NotaFiscal).all()  # Ajuste para filtro por usuário se implementado
        notas_json = [
            {
                "numero": nota.numero,
                "data_emissao": nota.data_emissao,
                "cnpj_emitente": nota.cnpj_emitente,
                "nome_emitente": nota.nome_emitente,
                "cnpj_destinatario": nota.cnpj_destinatario,
                "nome_destinatario": nota.nome_destinatario,
                "chave_nfe": nota.chave_nfe,
                "natureza_operacao": nota.natureza_operacao,
                "valor_total_nota": nota.valor_total_nota,
                "tipo_operacao": nota.tipo_operacao
            }
            for nota in notas
        ]

        # Prompt corrigido: Instrui IA a usar tipo_operacao
        prompt = f"""
        Você é um assistente fiscal. Responda à pergunta do usuário baseado nos dados das notas fiscais abaixo.
        Importante: Classifique notas de saída como aquelas com tipo_operacao='Saída' (o CNPJ do usuário {user_cnpj} é o emitente).
        Notas de entrada têm tipo_operacao='Entrada' (o CNPJ do usuário é o destinatário).
        NÃO use natureza_operacao para determinar entrada/saída, pois pode ser 'VENDA DE MERCADORIA' em ambos os casos.
        Use natureza_operacao apenas para descrever a transação.

        Dados das notas:
        {json.dumps(notas_json, indent=2, ensure_ascii=False)}

        Pergunta do usuário: {pergunta}

        Responda de forma clara e precisa, listando notas se solicitado.
        """
        
        resposta = chamar_gemini(prompt, api_key)
        logging.debug(f"RESPOSTA GEMINI CHAT: {resposta[:500]}...")
        return resposta

    except Exception as e:
        logging.error(f"ERRO AO PROCESSAR PERGUNTA CHAT: {e}")
        return f"Erro ao processar pergunta: {str(e)}"
    finally:
        session.close()