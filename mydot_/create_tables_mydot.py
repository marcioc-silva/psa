from app import create_app, db
from datetime import timedelta
from mydot.mydot_module.models.ponto import MyDotPunch  # noqa: F401

app = create_app()

with app.app_context():
    db.create_all()
    app.config["REMEMBER_COOKIE_DURATION"] = timedelta(days=30)
    print("OK: tabelas do MyDot criadas.")
