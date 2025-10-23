# src/processors/xml_processor.py
import xml.etree.ElementTree as ET
from datetime import datetime
import logging  # Para debug

logging.basicConfig(level=logging.DEBUG)

def processar_xml(caminho_arquivo, user_cnpj=""):
    """
    Parse XML NF-e 4.00 e retorna dict pra NotaFiscal + itens com impostos.
    Robustez pra variações de fornecedores (ex: ICMS00/ICMS10, IPI ausente).
    user_cnpj: CNPJ logado pra definir tipo_operacao (Entrada/Saída).
    """
    try:
        tree = ET.parse(caminho_arquivo)
        root = tree.getroot()
        ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}  # Namespace NF-e

        # Dados da nota (ide)
        ide = root.find('.//nfe:ide', ns)
        if ide is None:
            logging.error("Elemento 'ide' não encontrado.")
            return None
        numero = ide.find('nfe:nNF', ns).text if ide.find('nfe:nNF', ns) is not None else ''
        data_emissao_elem = ide.find('nfe:dhEmi', ns)
        data_emissao = data_emissao_elem.text[:10] if data_emissao_elem is not None else ''  # YYYY-MM-DD
        natureza_operacao = ide.find('nfe:natOp', ns).text if ide.find('nfe:natOp', ns) is not None else ''
        tp_nf = ide.find('nfe:tpNF', ns)
        tipo_base = 'Saída' if tp_nf is not None and tp_nf.text == '1' else 'Entrada'

        # Emitente
        emit = root.find('.//nfe:emit', ns)
        if emit is None:
            logging.error("Elemento 'emit' não encontrado.")
            return None
        cnpj_emitente = emit.find('nfe:CNPJ', ns).text if emit.find('nfe:CNPJ', ns) is not None else ''
        nome_emitente = emit.find('nfe:xNome', ns).text if emit.find('nfe:xNome', ns) is not None else ''
        ie_emitente = emit.find('nfe:IE', ns).text if emit.find('nfe:IE', ns) is not None else ''
        x_lgr = emit.find('.//nfe:xLgr', ns)
        nro = emit.find('.//nfe:nro', ns)
        x_bairro = emit.find('.//nfe:xBairro', ns)
        x_mun = emit.find('.//nfe:xMun', ns)
        uf = emit.find('.//nfe:UF', ns)
        endereco_emitente = f"{x_lgr.text if x_lgr is not None else ''} {nro.text if nro is not None else ''}, {x_bairro.text if x_bairro is not None else ''}, {x_mun.text if x_mun is not None else ''} - {uf.text if uf is not None else ''}"

        # Destinatário
        dest = root.find('.//nfe:dest', ns)
        cnpj_destinatario = dest.find('nfe:CNPJ', ns).text if dest.find('nfe:CNPJ', ns) is not None else None
        nome_destinatario = dest.find('nfe:xNome', ns).text if dest.find('nfe:xNome', ns) is not None else ''
        ie_destinatario = dest.find('nfe:IE', ns).text if dest.find('nfe:IE', ns) is not None else None
        x_lgr_dest = dest.find('.//nfe:xLgr', ns)
        nro_dest = dest.find('.//nfe:nro', ns)
        x_bairro_dest = dest.find('.//nfe:xBairro', ns)
        x_mun_dest = dest.find('.//nfe:xMun', ns)
        uf_dest = dest.find('.//nfe:UF', ns)
        endereco_destinatario = f"{x_lgr_dest.text if x_lgr_dest is not None else ''} {nro_dest.text if nro_dest is not None else ''}, {x_bairro_dest.text if x_bairro_dest is not None else ''}, {x_mun_dest.text if x_mun_dest is not None else ''} - {uf_dest.text if uf_dest is not None else ''}"

        # NOVO: Tipo_operacao baseado em user_cnpj vs emit/dest
        if user_cnpj:
            if user_cnpj == cnpj_emitente:
                tipo_operacao = 'Saída'
            elif user_cnpj == cnpj_destinatario:
                tipo_operacao = 'Entrada'
            else:
                tipo_operacao = 'Desconhecida'  # Raro, avisa no chat
            logging.debug(f"TIPO OPERACAO: User {user_cnpj} - Emit {cnpj_emitente} / Dest {cnpj_destinatario} = {tipo_operacao}")
        else:
            tipo_operacao = tipo_base  # Fallback

        # Totais (ICMSTot)
        icms_tot = root.find('.//nfe:ICMSTot', ns)
        if icms_tot is None:
            logging.error("Elemento 'ICMSTot' não encontrado.")
            return None
        valor_total_nota = icms_tot.find('nfe:vNF', ns).text if icms_tot.find('nfe:vNF', ns) is not None else '0.00'
        v_icms_total = icms_tot.find('nfe:vICMS', ns).text if icms_tot.find('nfe:vICMS', ns) is not None else '0.00'
        v_pis_total = icms_tot.find('nfe:vPIS', ns).text if icms_tot.find('nfe:vPIS', ns) is not None else '0.00'
        v_cofins_total = icms_tot.find('nfe:vCOFINS', ns).text if icms_tot.find('nfe:vCOFINS', ns) is not None else '0.00'

        # Chave (infNFe @Id)
        inf_nfe = root.find('.//nfe:infNFe', ns)
        chave_nfe = inf_nfe.get('Id').replace('NFe', '') if inf_nfe is not None else ''

        # Itens (det)
        itens = []
        dets = root.findall('.//nfe:det', ns)
        logging.debug(f"Encontrados {len(dets)} itens no XML.")
        for det in dets:
            n_item = det.get('nItem')
            prod = det.find('nfe:prod', ns)
            if prod is None:
                continue  # Pula det sem prod
            c_prod = prod.find('nfe:cProd', ns).text if prod.find('nfe:cProd', ns) is not None else ''
            x_prod = prod.find('nfe:xProd', ns).text if prod.find('nfe:xProd', ns) is not None else ''
            ncm = prod.find('nfe:NCM', ns).text if prod.find('nfe:NCM', ns) is not None else ''
            cfop = prod.find('nfe:CFOP', ns).text if prod.find('nfe:CFOP', ns) is not None else ''
            u_com = prod.find('nfe:uCom', ns).text if prod.find('nfe:uCom', ns) is not None else ''
            q_com = prod.find('nfe:qCom', ns).text if prod.find('nfe:qCom', ns) is not None else '0'
            v_un_com = prod.find('nfe:vUnCom', ns).text if prod.find('nfe:vUnCom', ns) is not None else '0.00'
            v_prod = prod.find('nfe:vProd', ns).text if prod.find('nfe:vProd', ns) is not None else '0.00'

            # Impostos do item (tenta ICMS00/ICMS10, PISAliq, COFINSAliq; default 0)
            icms_item = det.find('.//nfe:ICMS00', ns) or det.find('.//nfe:ICMS10', ns)  # Flex pra variações
            v_icms_item = float(icms_item.find('nfe:vICMS', ns).text if icms_item is not None and icms_item.find('nfe:vICMS', ns) is not None else '0.00')
            cst_icms = icms_item.find('nfe:CST', ns).text if icms_item is not None and icms_item.find('nfe:CST', ns) is not None else ''

            pis_item = det.find('.//nfe:PISAliq', ns)
            v_pis_item = float(pis_item.find('nfe:vPIS', ns).text if pis_item is not None and pis_item.find('nfe:vPIS', ns) is not None else '0.00')
            cst_pis = pis_item.find('nfe:CST', ns).text if pis_item is not None and pis_item.find('nfe:CST', ns) is not None else ''

            cofins_item = det.find('.//nfe:COFINSAliq', ns)
            v_cofins_item = float(cofins_item.find('nfe:vCOFINS', ns).text if cofins_item is not None and cofins_item.find('nfe:vCOFINS', ns) is not None else '0.00')
            cst_cofins = cofins_item.find('nfe:CST', ns).text if cofins_item is not None and cofins_item.find('nfe:CST', ns) is not None else ''

            # IPI (se presente, opcional)
            ipi_item = det.find('.//nfe:IPI', ns)
            v_ipi_item = float(ipi_item.find('.//nfe:vIPI', ns).text if ipi_item is not None and ipi_item.find('.//nfe:vIPI', ns) is not None else '0.00')
            cst_ipi = ipi_item.find('.//nfe:CST', ns).text if ipi_item is not None and ipi_item.find('.//nfe:CST', ns) is not None else cst_icms  # Fallback CST ICMS

            item = {
                'nota_id': None,  # Preenchido no save
                'codigo_produto': c_prod,
                'descricao_produto': x_prod,
                'ncm': ncm,
                'cst_ipi': cst_ipi,
                'cfop': cfop,
                'unidade': u_com,
                'quantidade': q_com,
                'valor_unitario': v_un_com,
                'valor_total': v_prod,
                'cst_icms': cst_icms,
                'cst_pis': cst_pis,
                'cst_cofins': cst_cofins,
                'cest': None,  # Não no XML sample
                # Impostos como Float
                'icms_valor': v_icms_item,
                'ipi_valor': v_ipi_item,
                'pis_valor': v_pis_item,
                'cofins_valor': v_cofins_item
            }
            itens.append(item)

        dados = {
            'numero': numero,
            'data_emissao': data_emissao,
            'cnpj_emitente': cnpj_emitente,
            'nome_emitente': nome_emitente,
            'ie_emitente': ie_emitente,
            'endereco_emitente': endereco_emitente,
            'cnpj_destinatario': cnpj_destinatario,
            'nome_destinatario': nome_destinatario,
            'ie_destinatario': ie_destinatario,
            'endereco_destinatario': endereco_destinatario,
            'chave_nfe': chave_nfe,
            'natureza_operacao': natureza_operacao,
            'valor_total_nota': valor_total_nota,
            'tipo_operacao': tipo_operacao,  # NOVO: Baseado em user_cnpj
            'versao': '4.00',
            'v_icms': v_icms_total,  # Total ICMS nota
            'v_pis': v_pis_total,
            'v_cofins': v_cofins_total,
            'itens': itens
        }

        logging.debug(f"XML PARSED: Nota {numero} - Tipo {tipo_operacao}, Valor R${valor_total_nota}, {len(itens)} itens, ICMS R${v_icms_total}")
        return dados

    except Exception as e:
        logging.error(f"ERRO PARSE XML: {e}")
        return None