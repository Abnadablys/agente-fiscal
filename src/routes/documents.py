# src/routes/documents.py

import os
import json
import re  # Pra regex stripping e clean CNPJ
import csv  # Pra ler CSV
import traceback
import logging  # Melhor que print para debug
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from database.connection import SessionLocal
from models.nota_fiscal import NotaFiscal, ItemNota

# Configura logging
logging.basicConfig(level=logging.DEBUG)

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
                cst_icms=item_data.get("cst_icms", ""),
                cst_pis=item_data.get("cst_pis", ""),
                cst_cofins=item_data.get("cst_cofins", ""),
                cest=item_data.get("cest", ""),
                # NOVO: Set impostos de item_data (do parser XML/CSV)
                icms_valor=float(item_data.get("icms_valor", 0)),
                ipi_valor=float(item_data.get("ipi_valor", 0)),
                pis_valor=float(item_data.get("pis_valor", 0)),
                cofins_valor=float(item_data.get("cofins_valor", 0))
            )
            session.add(item)
            logging.debug(f"ITEM SALVO: {item.descricao_produto} - ICMS R${item.icms_valor:.2f}, IPI R${item.ipi_valor:.2f}")

        session.commit()
        logging.debug(f"NOTA SALVA: {numero} - Total R${nota.valor_total_nota}, {len(itens)} itens")
        return {"ok": True}

    except Exception as e:
        session.rollback()
        logging.error(f"ERRO SALVAR NOTA: {e}")
        return {"ok": False, "reason": str(e)}
    finally:
        session.close()

def calcular_tipo_operacao(dados, user_cnpj):
    """
    Calcula tipo_operacao baseado em user_cnpj vs cnpj_emitente/destinatario.
    Usado para consistência em todos formatos.
    """
    if user_cnpj:
        if user_cnpj == dados.get("cnpj_emitente"):
            return "Saída"
        elif user_cnpj == dados.get("cnpj_destinatario"):
            return "Entrada"
        else:
            return "Desconhecida"
    return dados.get("tipo_operacao", "")  # Fallback se já setado ou desconhecido

@document_bp.route("/process-documents", methods=["POST"])
def process_documents():
    resultados = []
    uploaded_files = request.files.getlist("files")
    api_key = request.form.get("api_key", "")
    user_cnpj = request.form.get("user_cnpj", "")  # NOVO: Pegue do form se disponível (ex.: de auth)
    modelo = "gemini-2.5-flash"  # CORRIGIDO: Use versão válida; mude se for intencional 2.5

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
                    dados = processar_xml(caminho, user_cnpj=user_cnpj)  # Já calcula tipo_operacao
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
                logging.debug(f"TEXTO EXTRAÍDO PDF ({filename}): {texto[:500]}...")

                if not texto:
                    resultados.append({"arquivo": filename, "status": "PDF vazio ou erro extração"})
                    continue

                if api_key and chamar_gemini:
                    # PROMPT MELHORADO (adicionando campos faltantes)
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
                        "tipo_operacao": "Entrada/Saída",  # A IA infere, mas corrigiremos pós-parse
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
                                "cst_icms": "código",
                                "cst_pis": "código",
                                "cst_cofins": "código",
                                "cest": "código",
                                "icms_valor": número float,
                                "ipi_valor": número float,
                                "pis_valor": número float,
                                "cofins_valor": número float
                            }}
                        ]
                    }}
                    Se dados faltarem, use null. JSON Puro APENAS!
                    Texto do PDF: {texto}
                    """
                    resposta = chamar_gemini(prompt, api_key, modelo=modelo)
                    logging.debug(f"RESPOSTA IA PDF ({filename}): {resposta[:500]}...")

                    resposta_texto = resposta if isinstance(resposta, str) else (resposta.get("text") if isinstance(resposta, dict) else str(resposta))
                    
                    # Stripping robusto pra markdown e extras
                    resposta_texto = resposta_texto.strip()
                    resposta_texto = re.sub(r'^```json\s*', '', resposta_texto)  # Remove ```json no start
                    resposta_texto = re.sub(r'```\s*$', '', resposta_texto)  # Remove ``` no end
                    resposta_texto = re.sub(r'^\{|\}$', '', resposta_texto.strip())  # Extra safe para braces soltas
                    resposta_texto = '{' + resposta_texto + '}' if not resposta_texto.startswith('{') else resposta_texto

                    logging.debug(f"RESPOSTA APÓS STRIP PDF ({filename}): {resposta_texto[:500]}...")

                    # Try parse JSON
                    try:
                        dados = json.loads(resposta_texto)
                        # NOVO: Calcular tipo_operacao baseado em user_cnpj
                        dados["tipo_operacao"] = calcular_tipo_operacao(dados, user_cnpj)
                        logging.debug(f"JSON PARSED PDF ({filename}): {json.dumps(dados, indent=2)[:300]}...")
                        save_res = salvar_nota_no_db(dados)
                        if save_res.get("ok"):
                            resultados.append({"arquivo": filename, "status": "sucesso (PDF->IA->DB)"})
                        elif save_res.get("reason") == "duplicado":
                            resultados.append({"arquivo": filename, "status": "ignorado: nota duplicada"})
                        else:
                            resultados.append({"arquivo": filename, "status": f"erro salvar no DB: {save_res.get('reason')}"})
                    except json.JSONDecodeError as e:
                        logging.error(f"ERRO PARSE JSON PDF ({filename}): {e} - Resposta após strip: {resposta_texto[:200]}...")
                        
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
                        # NOVO: Calcular tipo_operacao no fallback
                        dados_fallback["tipo_operacao"] = calcular_tipo_operacao(dados_fallback, user_cnpj)
                        
                        logging.debug(f"FALLBACK DADOS PDF ({filename}): {dados_fallback}")
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

            # Processa CSV (igual anterior)
            elif filename.lower().endswith('.csv'):
                logging.debug(f"CSV LIDO ({filename}): Iniciando parse...")
                dados_notas = {}  # Agrupa por numero_nota + chave_acesso
                try:
                    with open(caminho, 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f, delimiter=';')  # delimiter=';' pra CSV BR
                        rows = list(reader)
                    
                    if rows:
                        logging.debug(f"PRIMEIRA ROW KEYS CSV ({filename}): {list(rows[0].keys())}")
                        logging.debug(f"PRIMEIRA ROW CSV ({filename}): {rows[0]}")
                    
                    for row in rows:
                        numero = row.get('numero_nota', '').strip()
                        chave = row.get('chave_acesso', '').strip()
                        item_num = row.get('item', '').strip()

                        if not numero or item_num == 'TOTAL':
                            if item_num == 'TOTAL' and numero:  # Linha TOTAL: Pega valor_total_nota
                                if numero in dados_notas:
                                    dados_notas[numero]['valor_total_nota'] = row.get('valor_total_nota', '')
                                    logging.debug(f"TOTAL SETADO pra nota {numero}: R${row.get('valor_total_nota', '')}")
                            continue  # Pula TOTAL ou vazias

                        key = f"{numero}_{chave}" if chave else numero  # Unique key
                        if key not in dados_notas:
                            dados_notas[key] = {
                                "numero": numero,
                                "data_emissao": row.get('data_emissao', ''),
                                "cnpj_emitente": re.sub(r'[^\d]', '', row.get('emitente_cnpj', '')),
                                "nome_emitente": row.get('emitente_razao_social', ''),
                                "ie_emitente": row.get('emitente_ie', ''),
                                "endereco_emitente": row.get('emitente_endereco', ''),
                                "cnpj_destinatario": re.sub(r'[^\d]', '', row.get('destinatario_cnpj', '')),
                                "nome_destinatario": row.get('destinatario_razao_social', ''),
                                "ie_destinatario": row.get('destinatario_ie', ''),
                                "endereco_destinatario": row.get('destinatario_endereco', ''),
                                "chave_nfe": chave,
                                "natureza_operacao": row.get('natureza_operacao', '') or row.get('tipo_operacao', ''),  # CORRIGIDO: Use coluna correta, fallback
                                "valor_total_nota": '',  # Setado na TOTAL
                                "tipo_operacao": '',  # Calculado pós-parse
                                "versao": row.get('serie', ''),  # Serie como versao approx
                                "itens": []
                            }

                        # Adiciona item se tem produto_codigo
                        if row.get('produto_codigo', ''):
                            item = {
                                "codigo_produto": row.get('produto_codigo', ''),
                                "descricao_produto": row.get('produto_descricao', ''),
                                "ncm": row.get('produto_ncm', ''),
                                "cfop": row.get('produto_cfop', ''),
                                "unidade": row.get('produto_unidade', ''),
                                "quantidade": row.get('produto_quantidade', ''),
                                "valor_unitario": row.get('produto_valor_unitario', ''),
                                "valor_total": row.get('produto_valor_total', ''),
                                "cst_icms": row.get('icms_cst', ''),
                                "cst_ipi": row.get('ipi_cst', ''),
                                "cst_pis": row.get('pis_cst', ''),
                                "cst_cofins": row.get('cofins_cst', ''),
                                "cest": row.get('cest', ''),
                                "icms_valor": float(row.get('icms_valor', 0)),
                                "ipi_valor": float(row.get('ipi_valor', 0)),
                                "pis_valor": float(row.get('pis_valor', 0)),
                                "cofins_valor": float(row.get('cofins_valor', 0))
                            }
                            dados_notas[key]["itens"].append(item)

                    logging.debug(f"DADOS PARSED CSV ({filename}): {len(dados_notas)} notas encontradas.")

                    # Calcular tipo_operacao para cada nota e salvar
                    for key, dados in dados_notas.items():
                        dados["tipo_operacao"] = calcular_tipo_operacao(dados, user_cnpj)  # NOVO: Calcula baseado em user_cnpj
                        save_res = salvar_nota_no_db(dados)
                        num = dados['numero']
                        if save_res.get("ok"):
                            resultados.append({"arquivo": filename, "nota": num, "status": "sucesso (CSV->DB)"})
                        else:
                            resultados.append({"arquivo": filename, "nota": num, "status": f"erro salvar: {save_res.get('reason')}"})

                except Exception as e:
                    logging.error(f"ERRO PARSE CSV ({filename}): {e}")
                    resultados.append({"arquivo": filename, "status": f"erro parsing CSV: {str(e)}"})

            else:
                resultados.append({"arquivo": filename, "status": "formato não suportado"})
                continue

        except Exception as e:
            traceback.print_exc()
            resultados.append({"arquivo": filename, "status": f"erro inesperado: {str(e)}"})
        finally:
            # NOVO: Limpe o arquivo temp para segurança
            if os.path.exists(caminho):
                os.remove(caminho)

    return jsonify(resultados)