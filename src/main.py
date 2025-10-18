from models.nota_fiscal import NotaFiscal, ItemNota  # Se ItemNota existir
from flask import Flask, render_template, redirect, session
from flask_cors import CORS
from routes.auth import auth_bp
from routes.documents import document_bp
from routes.chat import chat_bp
from models.usuario import Usuario
import os

# ADICIONE ESSES IMPORTS PARA O DB (ajuste o caminho se necessário)
from database.connection import engine, Base  # engine e Base do seu connection.py

app = Flask(__name__, static_folder="static", static_url_path="",)
app.secret_key = "secreto123"
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
    os.makedirs("src/temp", exist_ok=True)

    # ADICIONE ISSO AQUI: CRIAÇÃO DAS TABELAS NO BANCO
    with engine.connect() as connection:  # Conecta e cria tudo de uma vez
        Base.metadata.create_all(bind=engine)  # Cria tabelas se não existirem
    print("Banco de dados inicializado! Tabelas criadas com sucesso.")  # Para debug

    app.run(debug=True)
