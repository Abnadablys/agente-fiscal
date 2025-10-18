from sqlalchemy import Column, Integer, String
from database.connection import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cnpj = Column(String, unique=True, nullable=False)
    nome = Column(String, nullable=False)
    situacao_cadastral = Column(String)
    regime_tributario = Column(String)
    natureza_juridica = Column(String)
    senha = Column(String, nullable=False)  # 🔒 senha com hash bcrypt

    def __repr__(self):
        return f"<Usuario(nome='{self.nome}', cnpj='{self.cnpj}', regime='{self.regime_tributario}')>"
