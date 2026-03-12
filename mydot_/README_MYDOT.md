# MyDot (módulo Flask) — uso individual, pronto para evoluir para “industrial”

Este módulo adiciona um sistema de **registro de ponto por foto** ao seu app Flask (PSA), mantendo tudo **online**.

## Rotas
- `/mydot` — tela para registrar ponto (entrada/saída/pausa/retorno)
- `/mydot/history` — histórico do dispositivo (uso individual)
- `/mydot/export.csv` — exportação CSV do histórico (uso individual)
- `/mydot/health` — healthcheck (debug)

## Integração no seu PSA
1) Copie as pastas `app/routes`, `app/models`, `app/services`, `app/templates/mydot`, `app/static/mydot`.

2) Registre o blueprint (em `app/__init__.py` dentro de `create_app`), algo assim:

```python
from app.routes.mydot import bp as mydot_bp
app.register_blueprint(mydot_bp, url_prefix="/mydot")
```

3) Garanta que seu projeto já tem:
- `db` do SQLAlchemy (como você já usa)
- `flask_login` opcional (o módulo funciona **sem login** no modo individual)

4) Rode migrations:
- se você usa Flask-Migrate: `flask db migrate -m "add mydot"` e `flask db upgrade`
- se não usa: crie a tabela manualmente (ver model `MyDotPunch`)

## Modo individual vs industrial
Este módulo começa no **modo individual**:
- identifica o “usuário” por um `device_id` salvo em cookie.
- não exige login.
- geolocalização é opcional (config por env var).

Quando você quiser migrar para modo industrial, é só ligar as chaves e integrar com `Usuario` do PSA.

## Configuração por variáveis de ambiente
- `MYDOT_REQUIRE_LOGIN=0|1` (default 0)
- `MYDOT_REQUIRE_GEO=0|1` (default 0)
- `MYDOT_GEO_RADIUS_M=200` (default 200)
- `MYDOT_SITE_LAT=-21.207...` (setar depois)
- `MYDOT_SITE_LON=-50.448...` (setar depois)
- `MYDOT_UPLOAD_DIR=app/static/mydot/uploads` (default)

## Observações importantes
- Câmera no navegador/WebView exige **HTTPS**.
- A foto é enviada como base64 e salva como arquivo no servidor (mais leve que salvar no banco).
- Este módulo já registra IP, user-agent e hash da imagem (base para antifraude).


## Integração segura no PSA (sem impactar o PSA)

No `create_app()` do seu PSA (app/__init__.py), registre o blueprint com try/except:

```python
if app.config.get("ENABLE_MYDOT", True):
    try:
        from mydot.mydot_module.routes.mydot import bp as mydot_bp
        app.register_blueprint(mydot_bp, url_prefix="/mydot")
    except Exception as e:
        app.logger.warning(f"MyDot desabilitado (não impacta PSA): {e}")
```

### Static isolado
Os arquivos estáticos do MyDot são servidos em `/mydot-static/...` para não conflitar com o `/static` do PSA.

### Banco separado (opcional, recomendado no futuro)
Você pode isolar o MyDot em outro banco usando `SQLALCHEMY_BINDS` com a chave `mydot`.
Depois, adicione `__bind_key__ = "mydot"` no model `MyDotPunch`.
