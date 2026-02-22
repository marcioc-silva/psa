import os
import sys
 
from flask import render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from app.models.material import Usuario, MaterialPSA
# Ajuste de caminhos para garantir que a pasta 'app' seja encontrada
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app import create_app, db
# Importações unificadas

# Inicialização do App via Factory
app = create_app()
app.config['SECRET_KEY'] = 'uma-chave-muito-segura-da-nestle'

# Configuração de Segurança (Login)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' 

@login_manager.user_loader
def load_user(user_id):
    # Atualizado para evitar o LegacyAPIWarning
    return db.session.get(Usuario, int(user_id))

# Configuração Dinâmica do Banco de Dados
database_url = os.getenv("DATABASE_URL")
if database_url:
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
else:
    base_dir = os.path.abspath(os.path.dirname(__file__))
    db_path = os.path.join(base_dir, "app", "psa_storage.db")
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"

# --- MOTOR DE DADOS GLOBAL (KPIs) ---
@app.context_processor
def inject_global_metrics():
    if not current_user.is_authenticated or request.endpoint in ['login', 'registrar']:
        return {}

    data_filtro = request.args.get('data_filtro')
    
    # ALTERE DE: query = Material.query
    # PARA:
    query = MaterialPSA.query 
    
    if data_filtro:
        query = query.filter_by(data_importacao=data_filtro)

    total_base = query.count()
    conferidos_count = query.filter_by(conferido=True).count()
    anomalias_count = query.filter_by(possui_divergencia=True).count()
    
    # ALTERE DE: db.session.query(Material.data_importacao)
    # PARA:
    lista_datas = [d[0] for d in db.session.query(MaterialPSA.data_importacao).distinct().all() if d[0]]

    return dict(
        total=total_base,
        conferidos=conferidos_count,
        pendentes=total_base - conferidos_count,
        acuracidade=round((conferidos_count / total_base * 100), 1) if total_base > 0 else 0,
        taxa_qualidade=round(((total_base - anomalias_count) / total_base * 100), 1) if total_base > 0 else 100,
        itens_com_divergencia=anomalias_count,
        total_retencao=52, 
        datas=lista_datas,
        data_atual=data_filtro
    )

# --- ROTAS ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        sap = request.form.get('sap')
        senha = request.form.get('password')
        usuario = Usuario.query.filter_by(sap=sap).first()
        
        if usuario and usuario.verificar_senha(senha):
            login_user(usuario)
            return redirect(url_for('index'))
        
        flash('Erro: SAP ou Senha inválidos.')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    # Agora não precisamos passar 'total', 'conferidos', etc. O context_processor já faz isso!
    return render_template('index.html', nome=current_user.nome_completo)

@app.route('/registrar', methods=['GET', 'POST'])
def registrar():
    if request.method == 'POST':
        sap = request.form.get('sap')
        nome = request.form.get('nome')
        senha = request.form.get('password')
        
        if Usuario.query.filter_by(sap=sap).first():
            flash('Este SAP já está cadastrado!')
            return redirect(url_for('registrar'))

        novo_usuario = Usuario(sap=sap, nome_completo=nome, cargo='operador')
        novo_usuario.definir_senha(senha)
        
        db.session.add(novo_usuario)
        db.session.commit()

        flash('Cadastro realizado com sucesso!')
        return redirect(url_for('login'))

    return render_template('registrar.html')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)