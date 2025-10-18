# src/services/gemini_service.py
import os
from google import genai

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
