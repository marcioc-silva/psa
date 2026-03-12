from app import create_app, db
from datetime import timedelta
from mydot.mydot_module.models.ponto import MyDotPunch  # noqa: F401

app = create_app()

with app.app_context():
    from sqlalchemy import inspect
    inspector = inspect(db.engine)
    db.create_all()
    app.config["REMEMBER_COOKIE_DURATION"] = timedelta(days=30)
    print("OK: tabelas do MyDot criadas.")
    if 'mydot_punch' in inspector.get_table_names():
        cols = [c['name'] for c in inspector.get_columns('mydot_punch')]
        print(f"DEBUG: Colunas em mydot_punch: {cols}")