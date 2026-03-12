from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from flask import Blueprint,session, render_template, request, jsonify, make_response, redirect, url_for, flash
from sqlalchemy import desc
from app import db
from mydot.mydot_module.models.auth import MyDotColaborador
from mydot.mydot_module.models.config import MyDotConfig
from ..models.ponto import MyDotPunch
from mydot.mydot_module.helpers.auth_helper import mydot_login_required
from mydot.mydot_module.models.ponto import (
    MyDotPunch,
    MyDotBancoHoras,
    MyDotLancamentoBancoHoras,
    ConfiguracaoRH,
    ConfiguracaoAparencia,
)
from ..services.mydot_service import get_or_set_device_id
from mydot.mydot_module.models.ponto import ConfiguracaoRH, ConfiguracaoAparencia, MyDotBancoHoras
from mydot.mydot_module.helpers.helper_banco_horas import montar_resumo_banco_horas
from mydot.mydot_module.helpers.helper_aparencia import (
    obter_config_aparencia,
    inject_mydot_aparencia,

)
from mydot.mydot_module.helpers.helper_banco_horas import (
    recalcular_banco_horas,
    listar_banco_horas,
    formatar_minutos,
)
from mydot.mydot_module.helpers.auth_helper import (
    mydot_login_required,
    get_mydot_current_user,
    inject_mydot_user,
)
# Optional: se o PSA já usa flask_login, o módulo aproveita
try:
    from flask_login import login_required, current_user
except Exception:  # pragma: no cover
    login_required = None
    current_user = None

BASE_DIR = os.path.dirname(os.path.dirname(__file__))  # .../mydot_module
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

bp = Blueprint(
    "mydot",
    __name__,
    template_folder=TEMPLATES_DIR,
    static_folder=STATIC_DIR,
    static_url_path="/mydot-static"
)


@bp.context_processor
def contexto_aparencia():
    return inject_mydot_aparencia()

@bp.context_processor
def contexto_auth_mydot():
    return inject_mydot_user()


def _require_login() -> bool:
    return str(os.getenv("MYDOT_REQUIRE_LOGIN", "0")).strip() == "1"


@bp.get("/")
@mydot_login_required
def home():
    return render_template("mydot/home.html")


@bp.get("/history")
@mydot_login_required
def history():
    registros = (
        MyDotPunch.query
        .order_by(MyDotPunch.id.desc())
        .all()
    )

    historico = []

    for r in registros:
        data_fmt = "-"
        hora_fmt = "-"
        datetime_fmt = "-"

        try:
            if isinstance(r.ts_utc, datetime):
                dt = r.ts_utc
            elif isinstance(r.ts_utc, str):
                dt = datetime.strptime(r.ts_utc, "%Y-%m-%d %H:%M:%S")
            else:
                dt = None

            if dt is not None:
                data_fmt = dt.strftime("%d/%m/%Y")
                hora_fmt = dt.strftime("%H:%M:%S")
                datetime_fmt = dt.strftime("%d/%m/%Y %H:%M:%S")

        except Exception:
            datetime_fmt = str(r.ts_utc)

        historico.append({
            "id": r.id,
            "kind": r.kind,
            "device_id": r.device_id,
            "data": data_fmt,
            "hora": hora_fmt,
            "datetime": datetime_fmt,
            "ts_bruto": str(r.ts_utc),
        })

    return render_template("mydot/history.html", historico=historico)


@bp.get("/export.csv")
def export_csv():
    device_id = request.cookies.get("mydot_device_id")
    q = MyDotPunch.query

    if _require_login() and login_required and current_user and getattr(current_user, "is_authenticated", False):
        q = q.filter(MyDotPunch.user_id == getattr(current_user, "id", None))
        filename = "mydot_pontos_usuario.csv"
    else:
        if not device_id:
            return redirect(url_for("mydot.home"))
        q = q.filter(MyDotPunch.device_id == device_id)
        filename = "mydot_pontos_device.csv"

    punches = q.order_by(MyDotPunch.ts_utc.asc()).limit(2000).all()

    lines = ["id,data,hora,tipo"]
    for p in punches:
        ts_local = p.ts_utc.replace(tzinfo=timezone.utc).astimezone() if p.ts_utc else None
        data = ts_local.strftime("%d/%m/%Y") if ts_local else ""
        hora = ts_local.strftime("%H:%M") if ts_local else ""
        lines.append(f"{p.id},{data},{hora},{p.kind}")

    csv_text = "\n".join(lines) + "\n"
    resp = make_response(csv_text)
    resp.headers["Content-Type"] = "text/csv; charset=utf-8"
    resp.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


@bp.get("/health")
def health():
    return jsonify({"ok": True, "ts": datetime.now(timezone.utc).isoformat()})


@bp.route("/config", methods=["GET", "POST"])
@mydot_login_required
def config():
    resp = make_response()
    device_id = get_or_set_device_id(resp)

    cfg = MyDotConfig.query.filter_by(device_id=device_id).first()
    if not cfg:
        cfg = MyDotConfig(device_id=device_id)

    if request.method == "POST":
        cfg.daily_expected_minutes = int(request.form["daily"])
        cfg.min_lunch_minutes = int(request.form["lunch"])
        cfg.initial_balance_minutes = int(request.form["balance"])
        db.session.add(cfg)
        db.session.commit()

    resp.set_data(render_template("mydot/config.html", cfg=cfg))
    resp.mimetype = "text/html"
    return resp


@bp.get("/registrar")
@mydot_login_required
def registrar():
    return render_template("mydot/registrar.html")


# fuso oficial de São Paulo
TZ_BR = ZoneInfo("America/Sao_Paulo")


@bp.post("/registrar")
@mydot_login_required
def registrar_post():
    resp = make_response()
    device_id = get_or_set_device_id(resp)

    data = request.get_json(silent=True) or {}
    dt_local_str = (data.get("dt_local") or "").strip()

    try:
        if dt_local_str:
            # Ex.: "2026-03-09T15:30"
            dt_original = datetime.fromisoformat(dt_local_str)
        else:
            dt_original = datetime.now()

        # Solução drástica: subtrai 3 horas antes de gravar
        ts_gravar = dt_original  # - timedelta(hours=3)

    except ValueError:
        payload = {"ok": False, "error": "DT_LOCAL_INVALID"}
        resp.set_data(jsonify(payload).get_data())
        resp.mimetype = "application/json"
        return resp, 400

    last = (
        MyDotPunch.query
        .filter(
            MyDotPunch.device_id == device_id,
            MyDotPunch.ts_utc <= ts_gravar
        )
        .order_by(MyDotPunch.ts_utc.desc())
        .first()
    )

    kind = "entrada" if (not last or last.kind == "saida") else "saida"

    punch = MyDotPunch(
        device_id=device_id,
        kind=kind,
        ts_utc=ts_gravar
    )

    db.session.add(punch)
    db.session.commit()

    payload = {
        "ok": True,
        "id": punch.id,
        "kind": punch.kind,
        "data": ts_gravar.strftime("%d/%m/%Y"),
        "hora": ts_gravar.strftime("%H:%M:%S"),
        "datetime_formatado": ts_gravar.strftime("%d/%m/%Y %H:%M:%S"),
    }

    resp.set_data(jsonify(payload).get_data())
    resp.mimetype = "application/json"
    return resp


@bp.get("/history-json")
def history_json():
    registros = (
        MyDotPunch.query
        .order_by(MyDotPunch.id.desc())
        .all()
    )

    itens = []
    for r in registros:
        if isinstance(r.ts_utc, str):
            valor = r.ts_utc
        else:
            valor = r.ts_utc.strftime("%Y-%m-%d %H:%M:%S")

        itens.append({
            "id": r.id,
            "kind": r.kind,
            "ts": valor,
        })

    return jsonify(itens)


def obter_config_rh():
    config = ConfiguracaoRH.query.first()
    if not config:
        config = ConfiguracaoRH()
        db.session.add(config)
        db.session.commit()
    return config


@bp.route("/configuracoes/rh", methods=["GET", "POST"])
@mydot_login_required
def configuracoes_rh():
    config = obter_config_rh()

    if request.method == "POST":
        try:
            config.refeicao_minima_minutos = int(request.form.get("refeicao_minima_minutos", 60))
            config.interjornada_minima_horas = int(request.form.get("interjornada_minima_horas", 11))
            config.jornada_maxima_diaria_horas = int(request.form.get("jornada_maxima_diaria_horas", 10))
            config.jornada_padrao_minutos = int(request.form.get("jornada_padrao_minutos", 480))

            config.saldo_inicial_minutos = int(request.form.get("saldo_inicial_minutos", 0))
            config.saldo_atual_minutos = int(request.form.get("saldo_inicial_minutos", 0))

            config.tipo_escala = request.form.get("tipo_escala", "5x1_5x2")

            config.usar_domingo_folga_fixa = bool(request.form.get("usar_domingo_folga_fixa"))
            config.usar_sabado_alternado = bool(request.form.get("usar_sabado_alternado"))
            config.folga_dinamica_ativa = bool(request.form.get("folga_dinamica_ativa"))

            config.notificar_refeicao_invalida = bool(request.form.get("notificar_refeicao_invalida"))
            config.notificar_interjornada_invalida = bool(request.form.get("notificar_interjornada_invalida"))
            config.notificar_jornada_excedida = bool(request.form.get("notificar_jornada_excedida"))

            db.session.commit()
            flash("Configurações de RH salvas com sucesso!", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao salvar configurações de RH: {str(e)}", "danger")

        return redirect(url_for("mydot.configuracoes_rh"))

    return render_template("mydot/configuracoes_rh.html", config=config)


@bp.route("/configuracoes/aparencia", methods=["GET", "POST"])
@mydot_login_required
def configuracoes_aparencia():
    config = obter_config_aparencia()

    if request.method == "POST":
        try:
            config.nome_sistema = request.form.get("nome_sistema", "MyDot").strip()
            config.logo_url = request.form.get("logo_url", "").strip() or None
            config.cor_primaria = request.form.get("cor_primaria", "#0d6efd")
            config.cor_secundaria = request.form.get("cor_secundaria", "#6c757d")
            config.cor_fundo = request.form.get("cor_fundo", "#f8f9fa")
            config.cor_texto = request.form.get("cor_texto", "#212529")
            config.tema = request.form.get("tema", "claro")
            config.mensagem_boas_vindas = request.form.get("mensagem_boas_vindas", "").strip()
            config.favicon_url = request.form.get("favicon_url", "").strip() or None

            db.session.commit()
            flash("Configurações de aparência salvas com sucesso!", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao salvar aparência: {str(e)}", "danger")

        return redirect(url_for("mydot.configuracoes_aparencia"))

    return render_template("mydot/configuracoes_aparencia.html", config=config)


@bp.route("/config/rh")
@mydot_login_required
def config_rh():
    return render_template("mydot/configuracoes_rh.html")


@bp.route("/config/aparencia")
@mydot_login_required
def config_aparencia():
    return render_template("mydot/configuracoes_aparencia.html")

@bp.route("/banco-horas")
@mydot_login_required
def banco_horas():
    config = obter_config_rh()
    resumo = montar_resumo_banco_horas(config)

    return render_template(
        "mydot/banco_horas.html",
        resumo=resumo,
        config=config,
    )

@bp.route("/banco-horas/lancamento", methods=["GET", "POST"])
@mydot_login_required
def lancamento_banco_horas():
    if request.method == "POST":
        try:
            data_referencia = request.form.get("data_referencia", "").strip()
            observacao = request.form.get("observacao", "").strip() or None

            data_ref = datetime.strptime(data_referencia, "%Y-%m-%d").date()

            lancamento = MyDotLancamentoBancoHoras.query.filter_by(
                data_referencia=data_ref
            ).first()

            if not lancamento:
                lancamento = MyDotLancamentoBancoHoras(
                    data_referencia=data_ref,
                    tipo="folga_banco_horas",
                    observacao=observacao,
                )
                db.session.add(lancamento)
            else:
                lancamento.tipo = "folga_banco_horas"
                lancamento.observacao = observacao

            db.session.commit()
            flash("Folga por banco de horas lançada com sucesso.", "success")

        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao lançar folga por banco de horas: {str(e)}", "danger")

        return redirect(url_for("mydot.banco_horas"))

    return render_template("mydot/lancamento_banco_horas.html")

@bp.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if session.get("mydot_colaborador_id"):
        return redirect(url_for("mydot.home"))

    if request.method == "POST":
        sap = (request.form.get("sap") or "").strip()
        nome = (request.form.get("nome") or "").strip()
        senha = request.form.get("senha") or ""
        confirmar_senha = request.form.get("confirmar_senha") or ""

        if not sap or not nome or not senha or not confirmar_senha:
            flash("Preencha todos os campos.", "warning")
            return render_template("mydot/cadastro.html")

        if senha != confirmar_senha:
            flash("As senhas não coincidem.", "danger")
            return render_template("mydot/cadastro.html")

        existente = MyDotColaborador.query.filter_by(sap=sap).first()
        if existente:
            flash("Já existe um colaborador cadastrado com esse SAP.", "warning")
            return render_template("mydot/cadastro.html")

        try:
            colaborador = MyDotColaborador(
                sap=sap,
                nome=nome,
                ativo=True,
            )
            colaborador.set_senha(senha)

            db.session.add(colaborador)
            db.session.commit()

            session["mydot_colaborador_id"] = colaborador.id
            session["mydot_colaborador_nome"] = colaborador.nome
            session.permanent = True

            flash("Cadastro realizado com sucesso.", "success")
            return redirect(url_for("mydot.home"))

        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao realizar cadastro: {str(e)}", "danger")

    return render_template("mydot/cadastro.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("mydot_colaborador_id"):
        return redirect(url_for("mydot.home"))

    if request.method == "POST":
        sap = (request.form.get("sap") or "").strip()
        senha = request.form.get("senha") or ""

        colaborador = MyDotColaborador.query.filter_by(sap=sap).first()

        if not colaborador or not colaborador.check_senha(senha):
            flash("SAP ou senha inválidos.", "danger")
            return render_template("mydot/login.html")

        if not colaborador.ativo:
            flash("Usuário inativo.", "warning")
            return render_template("mydot/login.html")

        session["mydot_colaborador_id"] = colaborador.id
        session["mydot_colaborador_nome"] = colaborador.nome
        session.permanent = True

        flash("Login realizado com sucesso.", "success")
        return redirect(url_for("mydot.home"))

    return render_template("mydot/login.html")


@bp.route("/logout")
def logout():
    session.pop("mydot_colaborador_id", None)
    session.pop("mydot_colaborador_nome", None)
    flash("Você saiu do MyDot.", "info")
    return redirect(url_for("mydot.login"))