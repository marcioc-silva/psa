import os
from app import create_app, db

# 1. Pegamos a URL ANTES de criar a aplicação
database_url = os.getenv("DATABASE_URL")

# 2. Criamos a aplicação (A fábrica create_app deve receber ou buscar a config)
app = create_app()

# 3. Aplicamos a lógica de seleção que você enviou
if database_url:
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
else:
    # Ajuste o caminho para o banco do seu PSA
    base_dir = os.path.abspath(os.path.dirname(__file__))
    db_path = os.path.join(base_dir, "app", "psa_storage.db")
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"

# 4. AGORA SIM inicializamos e criamos as tabelas
with app.app_context():
    db.create_all()
    
    # Log de Inspeção para o Render
    print("-" * 30, flush=True)
    uri_final = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    origem = "NEON (Nuvem)" if "neon.tech" in uri_final else "SQLITE (Local)"
    print(f">>> INSPEÇÃO DE QUALIDADE: {origem}", flush=True)
    if "@" in uri_final:
        host = uri_final.split('@')[-1].split('/')[0]
        print(f">>> HOST ATIVO: {host}", flush=True)
    print("-" * 30, flush=True)

if __name__ == '__main__':
    # Roda localmente
    app.run(debug=True, host='0.0.0.0', port=5000)