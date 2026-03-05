from app import db

class MyDotConfig(db.Model):
    __bind_key__ = "mydot"
    __tablename__ = "mydot_config"

    id = db.Column(db.Integer, primary_key=True)

    device_id = db.Column(db.String(64), unique=True, nullable=False)

    daily_expected_minutes = db.Column(db.Integer, default=528)  # 8h48
    min_lunch_minutes = db.Column(db.Integer, default=60)

    min_rest_between_days_minutes = db.Column(db.Integer, default=660)  # 11h
    max_daily_minutes = db.Column(db.Integer, default=600)  # 10h
    max_continuous_minutes = db.Column(db.Integer, default=360)  # 6h
    mandatory_break_minutes = db.Column(db.Integer, default=15)

    initial_balance_minutes = db.Column(db.Integer, default=0)