import os
from app import create_app, db

# 1. Tenta capturar a URL do Neon
database_url = os.getenv("DATABASE_URL")

# 2. Se a URL não existir, forçamos o erro para diagnóstico
if not database_url:
    raise ValueError(">>> ERRO CRÍTICO: Variável DATABASE_URL não encontrada no Render!")

# 3. Tratamento obrigatório para o SQLAlchemy
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

# 4. Criamos a aplicação
app = create_app()

# 5. Injetamos a URL (Sem plano B para SQLite)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url

with app.app_context():
    try:
        # Tenta criar as tabelas no Neon
        db.create_all()
        
        print("-" * 30, flush=True)
        print(">>> TESTE DE ISOLAMENTO: POSTGRESQL ATIVO", flush=True)
        host = database_url.split('@')[-1].split('/')[0]
        print(f">>> CONECTADO EM: {host}", flush=True)
        print("-" * 30, flush=True)
        
    except Exception as e:
        # Se o erro for de senha, driver ou rede, aparecerá aqui:
        print("-" * 30, flush=True)
        print(f">>> FALHA NA CONEXÃO POSTGRESQL: {e}", flush=True)
        print("-" * 30, flush=True)
        # Encerra o processo para não rodar com erro
        exit(1)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)