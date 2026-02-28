from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, login_required
from datetime import datetime, timedelta, timezone
from sqlalchemy import func, case

from app.models.material import MaterialPSA
from app.models.usuario import Usuario
from app.services.scoping import scoped_material_query

bp = Blueprint("main", __name__)

def _parse_data_filtro(valor: str | None):
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

    base_q = scoped_material_query()

    if data_dt:
        base_q = base_q.filter(func.date(MaterialPSA.data_importacao) == data_dt)

    # Tabela
    materiais = base_q.order_by(MaterialPSA.data_importacao.desc()).all()

    # Cards em uma consulta (poka-yoke + performance + consistência)
    total, conferidos, pendentes, itens_com_divergencia = base_q.with_entities(
        func.count(MaterialPSA.id),
        func.sum(case((MaterialPSA.conferido.is_(True), 1), else_=0)),
        func.sum(case((MaterialPSA.conferido.isnot(True), 1), else_=0)),  # inclui NULL como pendente
        func.sum(case((MaterialPSA.possui_divergencia.is_(True), 1), else_=0)),
    ).one()

    total = int(total or 0)
    conferidos = int(conferidos or 0)
    pendentes = int(pendentes or 0)
    itens_com_divergencia = int(itens_com_divergencia or 0)

    acuracidade = round((conferidos / total * 100), 1) if total else 0
    taxa_qualidade = round(((total - itens_com_divergencia) / total * 100), 1) if total else 0

    # Retenção: use "agora" do banco (mais estável)
    limite = datetime.now(timezone.utc) - timedelta(days=30)

    total_retencao = base_q.filter(
        MaterialPSA.data_importacao.isnot(None),
        MaterialPSA.data_importacao < limite
    ).count()

    # Datas do seletor (sem filtro, mas com escopo)
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
        data_atual=data_filtro,
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
        sap_raw = request.form.get("sap", "")
        nome_raw = request.form.get("nome", "")
        senha = request.form.get("password", "")

        # Poka-yoke: normaliza e valida
        sap = sap_raw.strip()
        nome = nome_raw.strip()

        if not sap or not nome or not senha:
            flash("Preencha SAP, nome e senha.")
            return redirect(url_for("main.registrar"))

        # (Opcional) Poka-yoke: SAP só números (se isso fizer sentido no seu sistema)
        # if not sap.isdigit():
        #     flash("SAP inválido. Use apenas números.")
        #     return redirect(url_for("main.registrar"))

        # Poka-yoke: evita duplicidade por espaços/variações
        if Usuario.query.filter(func.trim(Usuario.sap) == sap).first():
            flash("Usuário já cadastrado.")
            return redirect(url_for("main.registrar"))

        novo_usuario = Usuario(sap=sap, nome_completo=nome)
        novo_usuario.set_senha(senha)

        try:
            # Poka-yoke anti-concorrência:
            # trava a tabela/linha de forma simples usando "FOR UPDATE" quando suportado
            # (no SQLite pode não ter efeito forte, mas no Postgres ajuda bastante).
            total_usuarios = (
                db.session.query(func.count(Usuario.id))
                .with_for_update()
                .scalar()
            )

            if (total_usuarios or 0) == 0:
                novo_usuario.cargo = "admin"

            db.session.add(novo_usuario)
            db.session.commit()

        except IntegrityError:
            db.session.rollback()
            flash("Não foi possível cadastrar. SAP já existe ou dados inválidos.")
            return redirect(url_for("main.registrar"))
        except Exception:
            db.session.rollback()
            flash("Erro ao cadastrar usuário. Tente novamente.")
            return redirect(url_for("main.registrar"))

        flash("Usuário cadastrado com sucesso!")
        return redirect(url_for("main.login"))

    return render_template("registrar.html")


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Você saiu do sistema.")
    return redirect(url_for("main.login"))


@bp.route("/relatorio_divergencias")
@login_required
def relatorio_divergencias():
    data_filtro_raw = request.args.get("data_filtro")
    data_filtro, data_dt = _parse_data_filtro(data_filtro_raw)

    # Universo com escopo + divergência
    query = scoped_material_query().filter(MaterialPSA.possui_divergencia.is_(True))

    if data_dt:
        query = query.filter(func.date(MaterialPSA.data_importacao) == data_dt)

    materiais = (
        query.order_by(
            MaterialPSA.data_importacao.desc(),
            MaterialPSA.unidade_deposito.asc()
        )
        .all()
    )

    return render_template(
        "relatorio_lista.html",
        materiais=materiais,
        data_atual=data_filtro
    )


@bp.route("/scanner")
@login_required
def scanner():
    return render_template("scanner.html")
