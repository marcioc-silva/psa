from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, login_required, logout_user
from datetime import datetime
from sqlalchemy import func

from app import db
from app.models.material import MaterialPSA
from app.models.usuario import Usuario
from app.services.scoping import scoped_material_query

bp = Blueprint("main", __name__)


def _parse_data_filtro(valor: str | None):
    """
    Converte 'YYYY-MM-DD' -> date.
    Poka-yoke: se vier inválido, retorna (None, None) e o sistema ignora o filtro.
    """
    if not valor:
        return None, None
    try:
        data_dt = datetime.strptime(valor, "%Y-%m-%d").date()
        return valor, data_dt
    except ValueError:
        return None, None


@bp.route("/")
@login_required
def dashboard():
    data_filtro_raw = request.args.get("data_filtro")
    data_filtro, data_dt = _parse_data_filtro(data_filtro_raw)

    # 1) Universo base (mesmo universo para tabela e cards)
    base_q = scoped_material_query()

    # 2) Filtro por data (apenas se válido)
    if data_dt:
        base_q = base_q.filter(func.date(MaterialPSA.data_importacao) == data_dt)

    # 3) Tabela
    materiais = base_q.order_by(MaterialPSA.data_importacao.desc()).all()

    # 4) Cards (contagens em SQL, sempre no mesmo universo)
    total = base_q.count()
    conferidos = base_q.filter(MaterialPSA.conferido.is_(True)).count()
    pendentes = base_q.filter(MaterialPSA.conferido.is_(False)).count()
    itens_com_divergencia = base_q.filter(MaterialPSA.possui_divergencia.is_(True)).count()

    acuracidade = round((conferidos / total * 100), 1) if total else 0
    taxa_qualidade = round(((total - itens_com_divergencia) / total * 100), 1) if total else 0

    # Retenção: itens com data_importacao > 30 dias (em SQL)
    hoje = datetime.now()
    total_retencao = base_q.filter(
        MaterialPSA.data_importacao.isnot(None),
        (func.julianday(hoje) - func.julianday(MaterialPSA.data_importacao)) > 30
    ).count()

    # 5) Datas no seletor: universo completo SEM filtro de data, mas respeitando escopo do usuário
    datas_q = (
        scoped_material_query()
        .with_entities(func.date(MaterialPSA.data_importacao))
        .filter(MaterialPSA.data_importacao.isnot(None))
        .distinct()
        .order_by(func.date(MaterialPSA.data_importacao).desc())
    )

    datas = [
        d[0].strftime("%Y-%m-%d") if hasattr(d[0], "strftime") else str(d[0])
        for d in datas_q.all()
    ]

    return render_template(
        "index.html",
        materiais=materiais,
        datas=datas,
        data_atual=data_filtro,  # string YYYY-MM-DD ou None
        total=total,
        conferidos=conferidos,
        pendentes=pendentes,
        acuracidade=acuracidade,
        taxa_qualidade=taxa_qualidade,
        itens_com_divergencia=itens_com_divergencia,
        total_retencao=total_retencao,
    )


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        sap = request.form.get("sap")
        senha = request.form.get("password")

        usuario = Usuario.query.filter_by(sap=sap).first()

        if usuario and usuario.verificar_senha(senha):
            login_user(usuario)
            return redirect(url_for("main.dashboard"))

        flash("SAP ou senha inválidos")

    return render_template("login.html")


@bp.route("/registrar", methods=["GET", "POST"])
def registrar():
    if request.method == "POST":
        sap = request.form.get("sap")
        nome = request.form.get("nome")
        senha = request.form.get("password")

        if not sap or not nome or not senha:
            flash("Preencha SAP, nome e senha.")
            return redirect(url_for("main.registrar"))

        if Usuario.query.filter_by(sap=sap).first():
            flash("Usuário já cadastrado.")
            return redirect(url_for("main.registrar"))

        novo_usuario = Usuario(sap=sap, nome_completo=nome)
        novo_usuario.set_senha(senha)

        # Regra simples: o primeiro usuário criado vira admin.
        if Usuario.query.count() == 0:
            novo_usuario.cargo = "admin"

        db.session.add(novo_usuario)
        db.session.commit()

        flash("Usuário cadastrado com sucesso!")
        return redirect(url_for("main.login"))

    return render_template("registrar.html")


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("main.login"))


@bp.route("/relatorio_divergencias")
@login_required
def relatorio_divergencias():
    data_filtro_raw = request.args.get("data_filtro")
    data_filtro, data_dt = _parse_data_filtro(data_filtro_raw)

    query = scoped_material_query().filter(MaterialPSA.possui_divergencia.is_(True))

    if data_dt:
        query = query.filter(func.date(MaterialPSA.data_importacao) == data_dt)

    materiais = query.order_by(
        MaterialPSA.data_importacao.desc(),
        MaterialPSA.unidade_deposito.asc()
    ).all()

    return render_template(
        "relatorio_lista.html",
        materiais=materiais,
        data_atual=data_filtro
    )


@bp.route("/scanner")
@login_required
def scanner():
    return render_template("scanner.html")
