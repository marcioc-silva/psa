from gunicorn import app

from app import create_app, db
from datetime import timedelta
from mydot.mydot_module.models.ponto import MyDotPunch  # noqa: F401

with app.app_context():
    from sqlalchemy import inspect
    
    # 1. Tenta deletar a tabela antiga para forçar a recriação correta
    # CUIDADO: Isso apaga os dados da tabela mydot_punch!
    db.session.execute(db.text("DROP TABLE IF EXISTS mydot_punch;"))
    db.session.commit()
    
    # 2. Cria tudo do zero com base no seu modelo Python atual
    db.create_all()
    
    # 3. Agora sim, inspeciona DEPOIS de criar
    inspector = inspect(db.engine)
    if 'mydot_punch' in inspector.get_table_names():
        cols = [c['name'] for c in inspector.get_columns('mydot_punch')]
        print(f"DEBUG_FINAL: Colunas em mydot_punch: {cols}")
    
    app.config["REMEMBER_COOKIE_DURATION"] = timedelta(days=30)
    print("OK: tabelas do MyDot recriadas com sucesso.")