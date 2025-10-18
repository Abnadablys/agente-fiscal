from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship
from database.connection import Base


class NotaFiscal(Base):
    __tablename__ = "notas_fiscais"

    id = Column(Integer, primary_key=True)
    numero = Column(String)
    data_emissao = Column(String)
    cnpj_emitente = Column(String)
    nome_emitente = Column(String)
    ie_emitente = Column(String)
    endereco_emitente = Column(String)
    cnpj_destinatario = Column(String)
    nome_destinatario = Column(String)
    ie_destinatario = Column(String)
    endereco_destinatario = Column(String)
    chave_nfe = Column(String, unique=True)
    natureza_operacao = Column(String)
    valor_total_nota = Column(String)
    tipo_operacao = Column(String)
    versao = Column(String)

    itens = relationship("ItemNota", back_populates="nota", cascade="all, delete-orphan")


class ItemNota(Base):
    __tablename__ = "itens_nota"

    id = Column(Integer, primary_key=True)
    nota_id = Column(Integer, ForeignKey("notas_fiscais.id"))
    codigo_produto = Column(String)
    descricao_produto = Column(String)
    ncm = Column(String)
    cst_ipi = Column(String)
    cfop = Column(String)
    unidade = Column(String)
    quantidade = Column(String)
    valor_unitario = Column(String)
    valor_total = Column(String)
    cst_icms = Column(String)
    cst_pis = Column(String)
    cst_cofins = Column(String)
    cest = Column(String)

    nota = relationship("NotaFiscal", back_populates="itens")
