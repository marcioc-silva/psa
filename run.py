from app import create_app, db
from routes_scanner_api import bp_scanner_api

app = create_app()
app.register_blueprint(bp_scanner_api)  # sem prefixo

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)