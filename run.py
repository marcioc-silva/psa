
from config import Config # Importação necessária para ler a URI
from app import create_app, db # Garanta que o db seja importado
import os

app = create_app()

with app.app_context():
    # 1. Verifica a URL (Igual ao seu finanças)
    db_uri = os.getenv("DATABASE_URL")
    
    if db_uri:
        # Se achou a variável do Neon, garante o postgresql://
        if db_uri.startswith("postgres://"):
            db_uri = db_uri.replace("postgres://", "postgresql://", 1)
        app.config["SQLALCHEMY_DATABASE_URI"] = db_uri
    
    # 2. Cria as tabelas se não existirem
    db.create_all()
    
    # 3. Log de Qualidade (O "olho" do supervisor)
    origem = "NEON (Nuvem)" if "neon.tech" in app.config["SQLALCHEMY_DATABASE_URI"] else "SQLITE (Local)"
    print(f">>> INSPEÇÃO DE BANCO: {origem}")

if __name__ == '__main__':
    print("-" * 30)
    print("SISTEMA PSA NESTLÉ ONLINE")
    print("-" * 30)
    
    # No Render, ele ignora o app.run e usa o Gunicorn, 
    # mas isso ajuda nos seus testes locais.
    app.run(debug=True, host='0.0.0.0', port=5000)