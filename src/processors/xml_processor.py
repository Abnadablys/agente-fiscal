# Lê o XML da NFe, extrai dados principais e salva no banco automaticamente.

import xml.etree.ElementTree as ET
from database.connection import SessionLocal
from models.nota_fiscal import NotaFiscal, ItemNota

def processar_xml(caminho_arquivo):
    """
    Processa um arquivo XML de NFe e salva os dados no banco.
    Retorna True se sucesso.
    """
    try:
        tree = ET.parse(caminho_arquivo)
        root = tree.getroot()

        ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}

        # Dados básicos da nota
        ide = root.find(".//nfe:ide", ns)
        emit = root.find(".//nfe:emit", ns)
        dest = root.find(".//nfe:dest", ns)
        total = root.find(".//nfe:ICMSTot", ns)

        numero = ide.findtext("nfe:nNF", "", ns)
        data_emissao = ide.findtext("nfe:dhEmi", "", ns)
        natureza_operacao = ide.findtext("nfe:natOp", "", ns)

        cnpj_emit = emit.findtext("nfe:CNPJ", "", ns)
        nome_emit = emit.findtext("nfe:xNome", "", ns)
        endereco_emit = emit.findtext("nfe:enderEmit/nfe:xLgr", "", ns)

        cnpj_dest = dest.findtext("nfe:CNPJ", "", ns)
        nome_dest = dest.findtext("nfe:xNome", "", ns)
        endereco_dest = dest.findtext("nfe:enderDest/nfe:xLgr", "", ns)

        valor_total = total.findtext("nfe:vNF", "0", ns)

        # Chave da nota
        chave = root.attrib.get("Id", "").replace("NFe", "")

        # Itens
        itens = []
        for det in root.findall(".//nfe:det", ns):
            prod = det.find("nfe:prod", ns)
            if prod is not None:
                itens.append({
                    "codigo_produto": prod.findtext("nfe:cProd", "", ns),
                    "descricao_produto": prod.findtext("nfe:xProd", "", ns),
                    "ncm": prod.findtext("nfe:NCM", "", ns),
                    "cfop": prod.findtext("nfe:CFOP", "", ns),
                    "quantidade": prod.findtext("nfe:qCom", "", ns),
                    "valor_unitario": prod.findtext("nfe:vUnCom", "", ns),
                    "valor_total": prod.findtext("nfe:vProd", "", ns),
                    "unidade": prod.findtext("nfe:uCom", "", ns)
                })

        # Salvar no banco
        session = SessionLocal()

        nota = NotaFiscal(
            numero=numero,
            data_emissao=data_emissao,
            cnpj_emitente=cnpj_emit,
            nome_emitente=nome_emit,
            endereco_emitente=endereco_emit,
            cnpj_destinatario=cnpj_dest,
            nome_destinatario=nome_dest,
            endereco_destinatario=endereco_dest,
            chave_nfe=chave,
            natureza_operacao=natureza_operacao,
            valor_total_nota=valor_total,
            tipo_operacao="Entrada/Saída"
        )

        for item in itens:
            nota.itens.append(ItemNota(**item))

        session.add(nota)
        session.commit()
        session.close()

        print(f"✅ XML processado e salvo: {numero}")
        return True

    except Exception as e:
        print(f"❌ Erro ao processar XML {caminho_arquivo}: {e}")
        return False
