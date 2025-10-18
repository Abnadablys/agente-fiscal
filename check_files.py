import os

expected = [
    "src/templates/login.html",
    "src/templates/register.html",
    "src/templates/dashboard.html",
    "src/templates/chat.html",
    "src/templates/upload.html",
    "src/static/styles/login.css",
    "src/static/styles/register.css",
    "src/static/styles/dashboard.css",
    "src/static/styles/chat.css",
    "src/static/scripts/login.js",
    "src/static/scripts/register.js",
    "src/static/scripts/chat.js",
    "src/static/scripts/upload.js",
    "src/main.py",
    "src/routes/auth.py",
    "src/routes/documents.py",
    "src/routes/chat.py",
    "src/models/usuario.py",
    "src/models/nota_fiscal.py",
    "src/database/connection.py",
    "init_db.py",
    "requirements.txt"
]

print("Verificando arquivos esperados...\n")
exists = []
missing = []
for p in expected:
    if os.path.exists(p):
        exists.append(p)
    else:
        missing.append(p)

print(f"✔️ Encontrados ({len(exists)}):")
for p in exists:
    print("  ", p)

print(f"\n❗ Faltando ({len(missing)}):")
for p in missing:
    print("  ", p)

# Sugestão sobre próximos passos
print("\n\nSe itens faltando forem apenas os templates estáticos (HTML/CSS/JS), posso gerar APENAS eles.")
print("Se faltar auth.py / main.py / modelos, diga quais prefere que eu gere primeiro.")
