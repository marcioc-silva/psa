from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app import db


class MyDotColaborador(UserMixin, db.Model):
    __bind_key__ = "mydot"
    __tablename__ = "mydot_colaboradores"

    id = db.Column(db.Integer, primary_key=True)
    sap = db.Column(db.String(30), unique=True, nullable=False, index=True)
    nome = db.Column(db.String(120), nullable=False)
    senha_hash = db.Column(db.String(255), nullable=False)
    ativo = db.Column(db.Boolean, default=True, nullable=False)

    criado_em = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def set_senha(self, senha: str) -> None:
        self.senha_hash = generate_password_hash(senha)

    def check_senha(self, senha: str) -> bool:
        return check_password_hash(self.senha_hash, senha)

    @property
    def is_active(self):
        return bool(self.ativo)

    def __repr__(self):
        return f"<MyDotColaborador id={self.id} sap={self.sap} nome={self.nome}>"