from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, login_required, logout_user
from app.models.material import MaterialPSA
from app.models.usuario import Usuario
from app import db
from datetime import datetime, timedelta  # Adicionado timedelta
from sqlalchemy import func

from app.services.scoping import scoped_material_query

bp = Blueprint('main', __name__)


@bp.route("/")
@login_required
def dashboard():
    data_filtro = request.args.get("data_filtro")  # esperado: DD-MM-YYYY

    # 1) Query base
    base_q = scoped_material_query()

    # 2) Aplica filtro de data
    data_dt = None
    if data_filtro:
        try:
            data_dt = datetime.strptime(data_filtro, "%d-%m-%Y").date()
            base_q = base_q.filter(func.date(MaterialPSA.data_importacao) == data_dt)
        except ValueError:
            data_filtro = None
            data_dt = None

    # 3) Tabela
    materiais = base_q.order_by(MaterialPSA.data_importacao.desc()).all()

    # 4) Cards
    total = base_q.count()
    conferidos = base_q.filter(MaterialPSA.conferido.is_(True)).count()
    pendentes = base_q.filter(MaterialPSA.conferido.is_(False)).count()
    itens_com_divergencia = base_q.filter(MaterialPSA.possui_divergencia.is_(True)).count()

    acuracidade = round((conferidos / total * 100), 1) if total else 0
    taxa_qualidade = round(((total - itens_com_divergencia) / total * 100), 1) if total else 0

    # --- CORREÇÃO DO ERRO JULIANDAY AQUI ---
    # Calculamos a data de corte (3 dias atrás) no Python
    data_corte = datetime.now() - timedelta(days=3)
    
    # Filtramos materiais onde a data de importação é anterior à data de corte
    total_retencao = base_q.filter(
        MaterialPSA.data_importacao.isnot(None),
        MaterialPSA.data_importacao < data_corte
    ).count()
    # ---------------------------------------

    # 5) Datas disponíveis no seletor
    datas_q = scoped_material_query().with_entities(func.date(MaterialPSA.data_importacao)).filter(
        MaterialPSA.data_importacao.isnot(None)
    ).distinct().order_by(func.date(MaterialPSA.data_importacao).desc())

    datas = [
        d[0].strftime("%d-%m-%Y") if hasattr(d[0], "strftime") else str(d[0])
        for d in datas_q.all()
    ]

    return render_template(
        "index.html",
        materiais=materiais,
        datas=datas,
        data_atual=data_filtro,
        total=total,
        conferidos=conferidos,
        pendentes=pendentes,
        acuracidade=acuracidade,
        taxa_qualidade=taxa_qualidade,
        itens_com_divergencia=itens_com_divergencia,
        total_retencao=total_retencao,
    )


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        sap = request.form.get('sap')
        senha = request.form.get('password')

        usuario = Usuario.query.filter_by(sap=sap).first()

        if usuario and usuario.verificar_senha(senha):
            login_user(usuario)
            return redirect(url_for('main.dashboard'))
        else:
            flash('SAP ou senha inválidos')

    return render_template('login.html')


@bp.route('/registrar', methods=['GET', 'POST'])
def registrar():
    if request.method == 'POST':
        sap = request.form.get('sap')
        nome = request.form.get('nome')
        senha = request.form.get('password')

        if Usuario.query.filter_by(sap=sap).first():
            flash('Usuário já cadastrado.')
            return redirect(url_for('main.registrar'))

        novo_usuario = Usuario(sap=sap, nome_completo=nome)
        novo_usuario.set_senha(senha)

        if Usuario.query.count() == 0:
            novo_usuario.cargo = 'admin'

        db.session.add(novo_usuario)
        db.session.commit()

        flash('Usuário cadastrado com sucesso!')
        return redirect(url_for('main.login'))

    return render_template('registrar.html')


@bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.login'))

@bp.route('/relatorio_divergencias')
@login_required
def relatorio_divergencias():
    divergencias = MaterialPSA.query.filter(MaterialPSA.possui_divergencia == True).all()
    return render_template('relatorio_lista.html', materiais=divergencias)

@bp.route('/scanner')
def scanner():
    return render_template('scanner.html')
