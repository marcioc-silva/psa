from app import create_app, db
from mydot.mydot_module.models.ponto import MyDotPunch  # noqa: F401

app = create_app()

with app.app_context():
    db.create_all()
    print("OK: tabelas do MyDot criadas.")
