from app import db
from datetime import datetime, timezone

class MyDotPunch(db.Model):
    __bind_key__ = "mydot"
    __tablename__ = "mydot_punch"

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(64), index=True, nullable=True)
    kind = db.Column(db.String(10), nullable=False)

    ts_utc = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    @property
    def ts_local(self):
        # converte UTC -> local do servidor (pode ajustar pra America/Sao_Paulo depois)
        return self.ts_utc.astimezone()