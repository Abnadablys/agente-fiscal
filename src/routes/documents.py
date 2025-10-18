# src/routes/documents.py

import os
import json
import re  # Pra regex stripping e clean CNPJ
import csv  # Pra ler CSV
import traceback
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from database.connection import SessionLocal
from models.nota_fiscal import NotaFiscal, ItemNota

# Importadores opcionais (se os módulos existirem)
try:
    from processors.xml_processor import processar_xml
except Exception:
    processar_xml = None

try:
    from processors.pdf_extractor import extrair_texto_pdf
except Exception:
    extrair_texto_pdf = None

# serviço que chama Gemini/Grok (implementar em services/gemini_service.py)
try:
    from services.gemini_service import chamar_gemini
except Exception:
    chamar_gemini = None


document_bp = Blueprint("document_bp", __name__)


def salvar_nota_no_db(dados_nota):
    """
    Espera um dict com campos da nota e uma lista 'itens'.
    Salva no banco usando SessionLocal.
    """

    session = SessionLocal()
    try:
        # Checagem simples de duplicidade: chave_nfe se fornecida, senão numero+cnpj_emitente+data_emissao
        chave = dados_nota.get("chave_nfe", "") or ""
        numero = str(dados_nota.get("numero", "")).strip()
        cnpj_emitente = str(dados_nota.get("cnpj_emitente", "")).strip()
        data_emissao = str(dados_nota.get("data_emissao", "")).strip()

        exists = None
        if chave:
            exists = session.query(NotaFiscal).filter_by(chave_nfe=chave).first()
        else:
            exists = session.query(NotaFiscal).filter_by(numero=numero, cnpj_emitente=cnpj_emitente, data_emissao=data_emissao).first()

        if exists:
            return {"ok": False, "reason": "duplicado"}

        nota = NotaFiscal(
            numero=numero,
            data_emissao=data_emissao,
            cnpj_emitente=cnpj_emitente,
            nome_emitente=dados_nota.get("nome_emitente", ""),
            ie_emitente=dados_nota.get("ie_emitente", ""),
            endereco_emitente=dados_nota.get("endereco_emitente", ""),
            cnpj_destinatario=dados_nota.get("cnpj_destinatario", ""),
            nome_destinatario=dados_nota.get("nome_destinatario", ""),
            ie_destinatario=dados_nota.get("ie_destinatario", ""),
            endereco_destinatario=dados_nota.get("endereco_destinatario", ""),
            chave_nfe=chave,
            natureza_operacao=dados_nota.get("natureza_operacao", ""),
            valor_total_nota=str(dados_nota.get("valor_total_nota", "")),
            tipo_operacao=dados_nota.get("tipo_operacao", ""),
            versao=dados_nota.get("versao", "")
        )

        session.add(nota)
        session.flush()  # Pega o ID da nota antes de commit

        # Salva itens se existirem
        itens = dados_nota.get("itens", [])
        for item_data in itens:
            item = ItemNota(
                nota_id=nota.id,  # FK
                codigo_produto=item_data.get("codigo_produto", ""),
                descricao_produto=item_data.get("descricao_produto", ""),
                ncm=item_data.get("ncm", ""),
                cst_ipi=item_data.get("cst_ipi", ""),
                cfop=item_data.get("cfop", ""),
                unidade=item_data.get("unidade", ""),
                quantidade=str(item_data.get("quantidade", "")),
                valor_unitario=str(item_data.get("valor_unitario", "")),
                valor_total=str(item_data.get("valor_total", "")),
                cest=item_data.get("cest", "")
            )
            session.add(item)

        session.commit()
        return {"ok": True}

    except Exception as e:
        session.rollback()
        print(f"DEBUG ERRO SALVAR NOTA: {e}")
        return {"ok": False, "reason": str(e)}
    finally:
        session.close()


@document_bp.route("/process-documents", methods=["POST"])
def process_documents():
    resultados = []
    uploaded_files = request.files.getlist("files")
    api_key = request.form.get("api_key", "")
    modelo = "gemini-2.5-flash"  # Padrão; ajuste se Grok

    for file in uploaded_files:
        filename = secure_filename(file.filename)
        if not filename:
            resultados.append({"arquivo": filename, "status": "nome inválido"})
            continue

        # Salva temp
        caminho = os.path.join("src/temp", filename)
        file.save(caminho)

        try:
            if filename.lower().endswith('.xml'):
                # Processa XML (igual antes)
                if processar_xml:
                    dados = processar_xml(caminho)
                    if dados:
                        save_res = salvar_nota_no_db(dados)
                        if save_res.get("ok"):
                            resultados.append({"arquivo": filename, "status": "sucesso (XML->DB)"})
                        else:
                            resultados.append({"arquivo": filename, "status": f"erro salvar no DB: {save_res.get('reason')}"})
                    else:
                        resultados.append({"arquivo": filename, "status": "erro parsing XML"})
                else:
                    resultados.append({"arquivo": filename, "status": "processador XML não implementado"})

            elif filename.lower().endswith('.pdf'):
                # Processa PDF (igual ao anterior, com stripping e fallback)
                if not extrair_texto_pdf:
                    resultados.append({"arquivo": filename, "status": "extrator PDF não implementado"})
                    continue

                texto = extrair_texto_pdf(caminho)
                print(f"DEBUG TEXTO EXTRAÍDO PDF ({filename}): {texto[:500]}...")  # Debug

                if not texto:
                    resultados.append({"arquivo": filename, "status": "PDF vazio ou erro extração"})
                    continue

                if api_key and chamar_gemini:
                    # PROMPT MELHORADO (igual anterior)
                    prompt = f"""
                    Extraia dados de Nota Fiscal Eletrônica de um PDF de texto. Retorne APENAS o JSON cru válido, SEM markdown, blocos de código (sem ```), texto extra ou explicações. Use estrutura exata:
                    {{
                        "numero": "número da NF",
                        "data_emissao": "YYYY-MM-DD",
                        "cnpj_emitente": "14 dígitos sem pontos",
                        "nome_emitente": "razão social",
                        "ie_emitente": "IE sem pontos",
                        "endereco_emitente": "endereço completo",
                        "cnpj_destinatario": "14 dígitos sem pontos",
                        "nome_destinatario": "nome",
                        "ie_destinatario": "IE sem pontos",
                        "endereco_destinatario": "endereço completo",
                        "chave_nfe": "44 dígitos",
                        "natureza_operacao": "descrição",
                        "valor_total_nota": número float sem R$,
                        "tipo_operacao": "Entrada/Saída",
                        "versao": "versão SEFAZ",
                        "itens": [
                            {{
                                "codigo_produto": "código",
                                "descricao_produto": "nome produto",
                                "ncm": "8 dígitos",
                                "cst_ipi": "código",
                                "cfop": "código",
                                "unidade": "UN",
                                "quantidade": número float,
                                "valor_unitario": número float sem R$,
                                "valor_total": número float sem R$,
                                "cest": "código"
                            }}
                        ]
                    }}
                    Se dados faltarem, use null. JSON Puro APENAS!
                    Texto do PDF: {texto}
                    """
                    resposta = chamar_gemini(prompt, api_key, modelo=modelo)
                    print(f"DEBUG RESPOSTA IA PDF ({filename}): {resposta[:500]}...")  # Debug

                    resposta_texto = resposta if isinstance(resposta, str) else (resposta.get("text") if isinstance(resposta, dict) else str(resposta))
                    
                    # Stripping robusto pra markdown
                    resposta_texto = resposta_texto.strip()
                    resposta_texto = re.sub(r'^```json\s*', '', resposta_texto)  # Remove ```json no start
                    resposta_texto = re.sub(r'```\s*$', '', resposta_texto)  # Remove ``` no end
                    resposta_texto = resposta_texto.strip()  # Limpa espaços extras

                    print(f"DEBUG RESPOSTA APÓS STRIP PDF ({filename}): {resposta_texto[:500]}...")  # Debug após clean

                    # Try parse JSON
                    try:
                        dados = json.loads(resposta_texto)
                        print(f"DEBUG JSON PARSED PDF ({filename}): {json.dumps(dados, indent=2)[:300]}...")  # Debug
                        save_res = salvar_nota_no_db(dados)
                        if save_res.get("ok"):
                            resultados.append({"arquivo": filename, "status": "sucesso (PDF->IA->DB)"})
                        elif save_res.get("reason") == "duplicado":
                            resultados.append({"arquivo": filename, "status": "ignorado: nota duplicada"})
                        else:
                            resultados.append({"arquivo": filename, "status": f"erro salvar no DB: {save_res.get('reason')}"})
                    except json.JSONDecodeError as e:
                        print(f"DEBUG ERRO PARSE JSON PDF ({filename}): {e} - Resposta após strip: {resposta_texto[:200]}...")  # Debug
                        
                        # FALLBACK: Parse manual simples do texto raw
                        dados_fallback = {}
                        match_num = re.search(r'Nº\s*(\d+)', texto)
                        dados_fallback["numero"] = match_num.group(1) if match_num else None
                        match_data = re.search(r'EMISSÃO:\s*(\d{2}/\d{2}/\d{4})', texto)
                        dados_fallback["data_emissao"] = match_data.group(1).replace('/', '-') if match_data else None
                        match_valor = re.search(r'VALOR TOTAL:\s*R\$\s*([\d.,]+)', texto)
                        dados_fallback["valor_total_nota"] = float(match_valor.group(1).replace('.', '').replace(',', '.')) if match_valor else None
                        match_cnpj_emit = re.search(r'CNPJ\s*([\d/.-]+)', texto)  # Ajuste se múltiplos
                        dados_fallback["cnpj_emitente"] = re.sub(r'[^\d]', '', match_cnpj_emit.group(1)) if match_cnpj_emit else None
                        dados_fallback["itens"] = []  # Sem itens no fallback
                        
                        print(f"DEBUG FALLBACK DADOS PDF ({filename}): {dados_fallback}")  # Debug
                        save_res = salvar_nota_no_db(dados_fallback)
                        if save_res.get("ok"):
                            resultados.append({"arquivo": filename, "status": "sucesso parcial (fallback sem itens)"})
                        else:
                            resultados.append({"arquivo": filename, "status": f"erro fallback: {save_res.get('reason')}"})
                else:
                    # Sem IA: salva .txt
                    try:
                        txtpath = caminho + ".txt"
                        with open(txtpath, "w", encoding="utf-8") as f:
                            f.write(texto)
                        resultados.append({"arquivo": filename, "status": "texto extraído (sem IA) salvo para análise"})
                    except Exception as e:
                        resultados.append({"arquivo": filename, "status": f"erro salvando texto: {str(e)}"})
                continue

            # CORRIGIDO: Processa CSV com ';' delimiter e layout específico
            elif filename.lower().endswith('.csv'):
                print(f"DEBUG CSV LIDO ({filename}): Iniciando parse...")  # Debug
                dados_notas = {}  # Agrupa por numero_nota + chave_acesso
                try:
                    with open(caminho, 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f, delimiter=';')  # CORRIGIDO: delimiter=';' pra CSV BR
                        rows = list(reader)
                    
                    if rows:
                        print(f"DEBUG PRIMEIRA ROW KEYS CSV ({filename}): {list(rows[0].keys())}")  # Debug headers
                        print(f"DEBUG PRIMEIRA ROW CSV ({filename}): {rows[0]}")  # Debug 1ª linha
                    
                    for row in rows:
                        numero = row.get('numero_nota', '').strip()
                        chave = row.get('chave_acesso', '').strip()
                        item_num = row.get('item', '').strip()

                        if not numero or item_num == 'TOTAL':
                            if item_num == 'TOTAL' and numero:  # Linha TOTAL: Pega valor_total_nota
                                if numero in dados_notas:
                                    dados_notas[numero]['valor_total_nota'] = row.get('valor_total_nota', '')
                                    print(f"DEBUG TOTAL SETADO pra nota {numero}: R${row.get('valor_total_nota', '')}")  # Debug
                            continue  # Pula TOTAL ou vazias

                        key = f"{numero}_{chave}" if chave else numero  # Unique key
                        if key not in dados_notas:
                            dados_notas[key] = {
                                "numero": numero,
                                "data_emissao": row.get('data_emissao', ''),
                                "cnpj_emitente": re.sub(r'[^\d]', '', row.get('emitente_cnpj', '')),  # Limpa pra 14 dígitos
                                "nome_emitente": row.get('emitente_razao_social', ''),
                                "ie_emitente": row.get('emitente_ie', ''),
                                "endereco_emitente": row.get('emitente_endereco', ''),
                                "cnpj_destinatario": re.sub(r'[^\d]', '', row.get('destinatario_cnpj', '')),
                                "nome_destinatario": row.get('destinatario_razao_social', ''),
                                "ie_destinatario": row.get('destinatario_ie', ''),
                                "endereco_destinatario": row.get('destinatario_endereco', ''),
                                "chave_nfe": chave,
                                "natureza_operacao": row.get('tipo_operacao', ''),
                                "valor_total_nota": '',  # Setado na TOTAL
                                "tipo_operacao": row.get('tipo_operacao', ''),
                                "versao": row.get('serie', ''),  # Serie como versao approx
                                "itens": []
                            }

                        # Adiciona item se tem produto_codigo
                        if row.get('produto_codigo', ''):
                            item = {
                                "codigo_produto": row.get('produto_codigo', ''),
                                "descricao_produto": row.get('produto_descricao', ''),
                                "ncm": row.get('produto_ncm', ''),
                                "cst_ipi": row.get('icms_aliquota', ''),  # Mapeia icms_aliquota pra cst_ipi (alíquota como str)
                                "cfop": row.get('produto_cfop', ''),
                                "unidade": row.get('produto_unidade', ''),
                                "quantidade": row.get('produto_quantidade', ''),
                                "valor_unitario": row.get('produto_valor_unitario', ''),
                                "valor_total": row.get('produto_valor_total', ''),
                                "cest": row.get('cest', '')  # Não no CSV
                            }
                            dados_notas[key]["itens"].append(item)

                    print(f"DEBUG DADOS PARSED CSV ({filename}): {len(dados_notas)} notas encontradas.")  # Debug

                    # Salva cada nota
                    for key, dados in dados_notas.items():
                        save_res = salvar_nota_no_db(dados)
                        num = dados['numero']
                        if save_res.get("ok"):
                            resultados.append({"arquivo": filename, "nota": num, "status": "sucesso (CSV->DB)"})
                        else:
                            resultados.append({"arquivo": filename, "nota": num, "status": f"erro salvar: {save_res.get('reason')}"})

                except Exception as e:
                    print(f"DEBUG ERRO PARSE CSV ({filename}): {e}")
                    resultados.append({"arquivo": filename, "status": f"erro parsing CSV: {str(e)}"})

            else:
                resultados.append({"arquivo": filename, "status": "formato não suportado"})
                continue

        except Exception as e:
            traceback.print_exc()
            resultados.append({"arquivo": filename, "status": f"erro inesperado: {str(e)}"})

    return jsonify(resultados)