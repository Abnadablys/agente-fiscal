from src.database.connection import engine, Base
from src.models.usuario import Usuario

print("🧱 Criando tabelas...")
Base.metadata.create_all(bind=engine)
print("✅ Banco de dados criado com sucesso!")
