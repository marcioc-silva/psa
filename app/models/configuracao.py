from __future__ import annotations

from datetime import datetime

from app import db


class ConfiguracaoSistema(db.Model):
    """Configuração global do sistema.

    A ideia é existir apenas 1 registro (id=1).
    """

    __tablename__ = "configuracao_sistema"

    id = db.Column(db.Integer, primary_key=True)

    # E-mail (remetente) - ÚNICO
    email_remetente = db.Column(db.String(255), nullable=True)
    nome_remetente = db.Column(db.String(255), nullable=True)

    # SMTP
    smtp_host = db.Column(db.String(255), nullable=True)
    smtp_port = db.Column(db.Integer, nullable=True)
    smtp_usuario = db.Column(db.String(255), nullable=True)
    smtp_senha = db.Column(db.String(255), nullable=True)
    smtp_tls = db.Column(db.Boolean, default=True)
    smtp_ssl = db.Column(db.Boolean, default=False)

    # Conteúdo
    assunto_padrao = db.Column(
        db.String(255),
        nullable=True,
        default="Reporte PSA - Nestlé Araçatuba",
    )

    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @staticmethod
    def get_singleton() -> "ConfiguracaoSistema":
        cfg = ConfiguracaoSistema.query.get(1)
        if not cfg:
            cfg = ConfiguracaoSistema(id=1)
            db.session.add(cfg)
            db.session.commit()
        return cfg


class EmailDestinatario(db.Model):
    """Lista de destinatários para o reporte (pode ter vários)."""

    __tablename__ = "email_destinatario"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    nome = db.Column(db.String(255), nullable=True)
    ativo = db.Column(db.Boolean, default=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
