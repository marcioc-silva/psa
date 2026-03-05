from app import db
from datetime import datetime
from zoneinfo import ZoneInfo

SP_TZ = ZoneInfo("America/Sao_Paulo")

class MyDotPunch(db.Model):
    __bind_key__ = "mydot"
    __tablename__ = "mydot_punch"

    id = db.Column(db.Integer, primary_key=True)

    # Identidade do dispositivo (controle pessoal)
    device_id = db.Column(db.String(64), index=True, nullable=False)

    # entrada/saida
    kind = db.Column(db.String(10), nullable=False)

    # horário LOCAL (SP) gravado no servidor (sem OCR)
    ts_local = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(SP_TZ).replace(tzinfo=None)  # salva “naive” em sqlite
    )