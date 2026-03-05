from app import db
from datetime import datetime

class MyDotPunch(db.Model):
    __bind_key__ = "mydot"
    __tablename__ = "mydot_punch"

    id = db.Column(db.Integer, primary_key=True)

    device_id = db.Column(db.String(64), index=True)

    kind = db.Column(db.String(10))  # in / out
    label = db.Column(db.String(40))  # interpretado

    ts_utc = db.Column(db.DateTime, default=datetime.utcnow)

    photo_path = db.Column(db.String(255))