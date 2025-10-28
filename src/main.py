# src/main.py
from .models.nota_fiscal import NotaFiscal, ItemNota
from flask import Flask, render_template, redirect, session
from flask_cors import CORS
from .routes.auth import auth_bp
from .routes.documents import document_bp
from .routes.chat import chat_bp
from .models.usuario import Usuario
from database.connection import engine, Base
import os
import secrets  # Para gerar chave secreta segura

app = Flask(__name__, static_folder="static", static_url_path="")
# Chave secreta segura para produção (não hardcode em prod; use variável de ambiente)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(16))
CORS(app)

# Registrar rotas
app.register_blueprint(auth_bp)
app.register_blueprint(document_bp, url_prefix="/api")
app.register_blueprint(chat_bp, url_prefix="/api")

# Página inicial -> redireciona para login.html
@app.route("/")
def index():
    if "cnpj" in session:
        return redirect("/dashboard")
    return render_template("login.html")

@app.route("/register")
def register():
    return render_template("register.html")

@app.route("/dashboard")
def dashboard():
    if "cnpj" not in session:
        return redirect("/")
    return render_template("dashboard.html")

@app.route("/chat")
def chat():
    if "cnpj" not in session:
        return redirect("/")
    return render_template("chat.html")

if __name__ == "__main__":
    # Cria diretório temporário para uploads
    os.makedirs("src/temp", exist_ok=True)

    # Inicializa banco de dados
    with engine.connect() as connection:
        Base.metadata.create_all(bind=engine)
    print("Banco de dados inicializado! Tabelas criadas com sucesso.")

    # Para desenvolvimento local apenas; em produção, Render usa Gunicorn
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_ENV") == "development")