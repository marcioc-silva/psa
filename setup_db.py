import sys
import os
# Adiciona a pasta raiz e a pasta models ao caminho
sys.path.append(os.getcwd())

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
# Importando direto da pasta models
from app.models.material import db, Usuario 

# Criamos uma instância temporária do App para o banco de dados
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///psa_storage.db' # Verifique se este é o nome do seu banco
db.init_app(app)

def criar_admin_inicial():
    with app.app_context():
        db.create_all()
        
        meu_sap = "11022431" 
        admin_existente = Usuario.query.filter_by(sap=meu_sap).first()

        if not admin_existente:
            novo_admin = Usuario(
                sap=meu_sap,
                nome_completo="Marcio Correa da Silva",
                cargo="admin"
            )
            novo_admin.definir_senha("10041984") 
            
            db.session.add(novo_admin)
            db.session.commit()
            print(f"Sucesso! Admin SAP {meu_sap} criado.")
        else:
            print(f"O SAP {meu_sap} já existe.")

if __name__ == "__main__":
    criar_admin_inicial()