from datetime import datetime

from app import db


class ConfiguracaoSistema(db.Model):
    """Configuração global do sistema.

    A ideia é ser uma tabela singleton (id=1), fácil de extender depois.
    """

    __tablename__ = 'configuracao_sistema'

    id = db.Column(db.Integer, primary_key=True)

    # E-mail do gerente/supervisor para receber relatórios
    email_gerente = db.Column(db.String(255), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    @staticmethod
    def get_singleton():
        cfg = ConfiguracaoSistema.query.get(1)
        if not cfg:
            cfg = ConfiguracaoSistema(id=1, email_gerente=None)
            db.session.add(cfg)
            db.session.commit()
        return cfg
