import os

class Config:
    # Chave de segurança para sessões e mensagens flash
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'chave-super-secreta-dev'
    
    # Captura a URL do Neon (configurada no Render) ou usa o SQLite local
    uri = os.environ.get('DATABASE_URL')
    
    if uri:
        # Correção técnica: O SQLAlchemy exige 'postgresql://' 
        # mas o Neon/Render podem enviar 'postgres://'
        if uri.startswith("postgres://"):
            uri = uri.replace("postgres://", "postgresql://", 1)
        SQLALCHEMY_DATABASE_URI = uri
    else:
        # Banco de dados local para quando você estiver testando no seu PC
        SQLALCHEMY_DATABASE_URI = 'sqlite:///psa_storage.db'

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Atualizado para a versão com banco de dados persistente
    VERSION = "1.3.0"

    