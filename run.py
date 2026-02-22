from app import create_app
from config import Config # Importação necessária para ler a URI

# Criamos a instância da aplicação
app = create_app()

with app.app_context():
    from app import db
    try:
        db.create_all()
        print(">>> Banco de dados sincronizado com sucesso!")
        
        # Correção aqui: Usamos Config (com C maiúsculo)
        if Config.SQLALCHEMY_DATABASE_URI:
            db_host = Config.SQLALCHEMY_DATABASE_URI.split('@')[-1].split('/')[0]
            print(f">>> SISTEMA PSA CONECTADO EM: {db_host}")
    except Exception as e:
        print(f">>> ERRO AO CONECTAR NO BANCO: {e}")

if __name__ == '__main__':
    print("-" * 30)
    print("SISTEMA PSA NESTLÉ ONLINE")
    print("-" * 30)
    
    # No Render, ele ignora o app.run e usa o Gunicorn, 
    # mas isso ajuda nos seus testes locais.
    app.run(debug=True, host='0.0.0.0', port=5000)