from flask import Blueprint, request, jsonify, session
from database.connection import SessionLocal
from models.usuario import Usuario
import requests
import bcrypt

auth_bp = Blueprint("auth_bp", __name__)

# 🔹 Função auxiliar: consulta dados da empresa pelo CNPJ
def consultar_dados_cnpj(cnpj: str):
    try:
        response = requests.get(f"https://publica.cnpj.ws/cnpj/{cnpj}")
        if response.status_code != 200:
            return None
        return response.json()
    except Exception as e:
        print(f"Erro ao consultar CNPJ: {e}")
        return None


# 🔹 Rota: CADASTRO
@auth_bp.route("/register", methods=["POST"])
def register_user():
    data = request.get_json()
    cnpj = data.get("cnpj", "").replace(".", "").replace("/", "").replace("-", "")
    senha = data.get("senha", "")

    if not cnpj.isdigit() or len(cnpj) != 14:
        return jsonify({"erro": "CNPJ inválido"}), 400
    if not senha:
        return jsonify({"erro": "Senha obrigatória"}), 400

    db = SessionLocal()

    # Evita duplicidade
    if db.query(Usuario).filter_by(cnpj=cnpj).first():
        db.close()
        return jsonify({"erro": "CNPJ já cadastrado"}), 409

    dados = consultar_dados_cnpj(cnpj)
    if not dados:
        db.close()
        return jsonify({"erro": "Erro ao consultar API de CNPJ"}), 500

    # Extrai os dados principais
    nome = dados.get("razao_social", "")
    natureza = dados.get("natureza_juridica", {}).get("descricao", "")
    situacao = dados.get("estabelecimento", {}).get("situacao_cadastral", "")
    simples = dados.get("simples", {})

    if simples.get("simples_nacional") and simples["simples_nacional"].get("mei"):
        regime = "MEI"
    else:
        regime = "Simples Nacional"

    senha_hash = bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    novo_usuario = Usuario(
        cnpj=cnpj,
        nome=nome,
        natureza_juridica=natureza,
        situacao_cadastral=situacao,
        regime_tributario=regime,
        senha=senha_hash
    )

    db.add(novo_usuario)
    db.commit()
    db.close()

    return jsonify({"mensagem": "Usuário cadastrado com sucesso!"}), 201


# 🔹 Rota: LOGIN
@auth_bp.route("/login", methods=["POST"])
def login_user():
    data = request.get_json()
    cnpj = data.get("cnpj", "").replace(".", "").replace("/", "").replace("-", "")
    senha = data.get("senha", "")

    db = SessionLocal()
    usuario = db.query(Usuario).filter_by(cnpj=cnpj).first()

    if not usuario:
        db.close()
        return jsonify({"erro": "Usuário não encontrado"}), 404

    if not bcrypt.checkpw(senha.encode("utf-8"), usuario.senha.encode("utf-8")):
        db.close()
        return jsonify({"erro": "Senha incorreta"}), 401

    # Guarda o CNPJ logado na sessão
    session["cnpj"] = usuario.cnpj

    db.close()
    return jsonify({
        "mensagem": "Login realizado com sucesso!",
        "usuario": {
            "nome": usuario.nome,
            "regime": usuario.regime_tributario,
            "natureza": usuario.natureza_juridica
        }
    }), 200

# 🔹 NOVA ROTA: DADOS DO USUÁRIO LOGADO (para o dashboard)
@auth_bp.route("/api/usuario_dados", methods=["GET"])
def get_usuario_dados():
    if "cnpj" not in session:
        return jsonify({"erro": "Não autorizado"}), 401
    
    cnpj = session["cnpj"]
    db = SessionLocal()
    usuario = db.query(Usuario).filter_by(cnpj=cnpj).first()
    
    if not usuario:
        db.close()
        return jsonify({"erro": "Usuário não encontrado"}), 404
    
    db.close()
    return jsonify({
        "nome": usuario.nome,
        "regime": usuario.regime_tributario,
        "natureza": usuario.natureza_juridica
    }), 200

# 🔹 Rota: LOGOUT
@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"mensagem": "Logout efetuado com sucesso"}), 200
