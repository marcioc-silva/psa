from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from flask import Blueprint, render_template, request, jsonify, make_response, redirect, url_for
from sqlalchemy import desc
from app import db
from mydot.mydot_module.models.config import MyDotConfig
from ..models.ponto import MyDotPunch
from ..services.mydot_service import get_or_set_device_id

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


def _require_login() -> bool:
    return str(os.getenv("MYDOT_REQUIRE_LOGIN", "0")).strip() == "1"


@bp.get("/")
def home():
    return render_template("mydot/home.html")


@bp.get("/history")
def history():
    device_id = request.cookies.get("mydot_device_id")
    q = MyDotPunch.query

    if _require_login() and login_required and current_user and getattr(current_user, "is_authenticated", False):
        q = q.filter(MyDotPunch.user_id == getattr(current_user, "id", None))
        subject = f"Usuário {getattr(current_user, 'nome_completo', 'logado')}"
    else:
        if not device_id:
            return redirect(url_for("mydot.home"))
        q = q.filter(MyDotPunch.device_id == device_id)
        subject = f"Dispositivo {device_id[:8]}…"

    punches = q.order_by(desc(MyDotPunch.ts_utc)).limit(300).all()
    from mydot.mydot_module.services.mydot_engine import compute, RhRules

    rules = RhRules(
        daily_expected_minutes=480,
        min_lunch_minutes=60,
    )

    engine = compute(punches, rules=rules)

# agora você tem:
# engine.days -> lista por dia com worked/breaks/delta/flags
# engine.total_delta -> saldo total
    return render_template("mydot/history.html", punches=punches, subject=subject)


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
def registrar():
    return render_template("mydot/registrar.html")


@bp.post("/registrar")
def registrar_post():
    resp = make_response()
    device_id = get_or_set_device_id(resp)

    data = request.get_json(silent=True) or {}
    dt_local_str = (data.get("dt_local") or "").strip()

    if dt_local_str:
        try:
            dt_naive = datetime.fromisoformat(dt_local_str)  # "YYYY-MM-DDTHH:MM"
            ts = dt_naive.replace(tzinfo=TZ_BR).astimezone(timezone.utc)
        except ValueError:
            resp.set_data(jsonify({"ok": False, "error": "DT_LOCAL_INVALID"}).get_data())
            resp.mimetype = "application/json"
            return resp, 400
    else:
        ts = datetime.now(timezone.utc)

    last = (
        MyDotPunch.query
        .filter(MyDotPunch.device_id == device_id, MyDotPunch.ts_utc <= ts)
        .order_by(MyDotPunch.ts_utc.desc())
        .first()
    )
    kind = "entrada" if (not last or last.kind == "saida") else "saida"

    punch = MyDotPunch(device_id=device_id, kind=kind, ts_utc=ts)
    db.session.add(punch)
    db.session.commit()

    ts_br = ts.astimezone(ZoneInfo("America/Sao_Paulo"))

    payload = {
        "ok": True,
        "id": punch.id,
        "kind": punch.kind,
        "data": ts_br.strftime("%d/%m/%Y"),
        "hora": ts_br.strftime("%H:%M"),
    }
    print("-" * 30)    
    print(f"HORA ORIGINAL (SERVIDOR): {ts_br.strftime('%H:%M:%S')}")
    print(f"HORA CALCULADA (SAO PAULO): {payload['hora']}")
    print(f"PAYLOAD COMPLETO: {payload}")
    print("-" * 30)
    resp.set_data(jsonify(payload).get_data())
    resp.mimetype = "application/json"
    return resp