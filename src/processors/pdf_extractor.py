# Extrai texto bruto de PDFs (usando pdfplumber), útil para enviar ao Gemini.

import pdfplumber

def extrair_texto_pdf(caminho_pdf):
    """
    Extrai o texto de um arquivo PDF.
    Retorna uma string com o texto completo.
    """
    try:
        texto = ""
        with pdfplumber.open(caminho_pdf) as pdf:
            for pagina in pdf.pages:
                texto += pagina.extract_text() + "\n"
        return texto.strip()
    except Exception as e:
        return f"Erro ao ler PDF: {str(e)}"
