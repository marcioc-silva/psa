from config import Config
from app import create_app, db
import os

# 1. Inicializamos a aplicação
app = create_app()

# 2. Configuração de Diagnóstico e Inicialização de Banco
# Colocamos fora do __main__ para garantir que o Gunicorn execute no Render
with app.app_context():
    # Buscamos a variável de ambiente configurada no painel do Render
    db_uri = os.getenv("DATABASE_URL")
    
    if db_uri:
        # Se achou a variável do Neon, garante o prefixo 'postgresql://'
        if db_uri.startswith("postgres://"):
            db_uri = db_uri.replace("postgres://", "postgresql://", 1)
        
        # Sobrescrevemos a configuração para garantir a conexão com a nuvem
        app.config["SQLALCHEMY_DATABASE_URI"] = db_uri
    
    try:
        # Cria as tabelas no Neon (se não existirem) seguindo sua estrutura SQL
        db.create_all()
        
        # Log de Qualidade (O "olho" do supervisor)
        # O flush=True força a exibição imediata nos logs do Render
        print("-" * 30, flush=True)
        uri_final = app.config.get("SQLALCHEMY_DATABASE_URI", "")
        origem = "NEON (Nuvem)" if "neon.tech" in uri_final else "SQLITE (Local)"
        print(f">>> INSPEÇÃO DE BANCO: {origem}", flush=True)
        
        # Exibe o host para conferência técnica (sem exibir a senha por segurança)
        if "@" in uri_final:
            print(f">>> HOST: {uri_final.split('@')[-1].split('/')[0]}", flush=True)
        print("-" * 30, flush=True)
        
    except Exception as e:
        print(f">>> ERRO CRÍTICO NA CONEXÃO: {e}", flush=True)

# 3. Execução Local
if __name__ == '__main__':
    print("-" * 30)
    print("SISTEMA PSA NESTLÉ - MODO DESENVOLVEDOR")
    print("-" * 30)
    
    # Rodando o servidor localmente na porta 5000
    app.run(debug=True, host='0.0.0.0', port=5000)