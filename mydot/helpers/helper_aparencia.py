from app import db
from mydot.mydot_module.models.mydot import ConfiguracaoAparencia


def obter_config_aparencia():
    config = ConfiguracaoAparencia.query.first()
    if not config:
        config = ConfiguracaoAparencia()
        db.session.add(config)
        db.session.commit()
    return config


def inject_mydot_aparencia():
    try:
        config_aparencia = obter_config_aparencia()
    except Exception:
        config_aparencia = None

    return {"mydot_aparencia": config_aparencia}