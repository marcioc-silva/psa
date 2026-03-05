from __future__ import annotations

import os
import uuid
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from flask import (
    Blueprint, current_app, render_template, request, jsonify,
    make_response, redirect, url_for, send_file
)
from sqlalchemy import desc
from werkzeug.utils import secure_filename

from app import db
from mydot.mydot_module.models.config import MyDotConfig
from ..models.ponto import MyDotPunch
from ..services.mydot_service import (
    get_or_set_device_id, parse_geo, geo_within_radius_m,
    ensure_upload_dir, save_base64_image_jpeg
)

# Optional: se o PSA já usa flask_login, o módulo aproveita
try:
    from flask_login import login_required, current_user
except Exception:  # pragma: no cover
    login_required = None
    current_user = None

# Blueprint isolado: templates/static do MyDot (não conflita com PSA)
BASE_DIR = os.path.dirname(os.path.dirname(__file__))  # .../mydot_module
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

bp = Blueprint(
    "mydot",
    __name__,
    template_folder="../templates",
    static_folder="../static",
    static_url_path="/mydot-static"
)



def _require_login() -> bool:
    return str(os.getenv("MYDOT_REQUIRE_LOGIN", "0")).strip() == "1"


def _require_geo() -> bool:
    return str(os.getenv("MYDOT_REQUIRE_GEO", "0")).strip() == "1"


@bp.get("/")
def home():
    return render_template("mydot/home.html")


@bp.get("/history")
def history():
    device_id = request.cookies.get("mydot_device_id")
    q = MyDotPunch.query

    # Se login estiver ativo, usa user_id; senão usa device_id
    if _require_login() and login_required and current_user and getattr(current_user, "is_authenticated", False):
        q = q.filter(MyDotPunch.user_id == getattr(current_user, "id", None))
        subject = f"Usuário {getattr(current_user, 'nome_completo', 'logado')}"
    else:
        if not device_id:
            return redirect(url_for("mydot.home"))
        q = q.filter(MyDotPunch.device_id == device_id)
        subject = f"Dispositivo {device_id[:8]}…"

    punches = q.order_by(desc(MyDotPunch.ts_utc)).limit(300).all()
    return render_template("mydot/history.html", punches=punches, subject=subject)


@bp.get("/export.csv")
def export_csv():
    # Exporta os últimos registros do device (modo individual) ou do usuário (modo login)
    device_id = request.cookies.get("mydot_device_id")
    q = MyDotPunch.query

    if _require_login() and login_required and current_user and getattr(current_user, "is_authenticated", False):
        q = q.filter(MyDotPunch.user_id == getattr(current_user, "id", None))
        filename = "mydot_pontos_usuario.csv"
    else:
        if not device_id:
            return redirect(url_for("mydot.index"))
        q = q.filter(MyDotPunch.device_id == device_id)
        filename = "mydot_pontos_device.csv"

    punches = q.order_by(MyDotPunch.ts_utc.asc()).limit(2000).all()

    # Gera CSV simples em memória
    lines = ["id,ts_utc,tipo,lat,lon,ip,user_agent,foto_path,hash_img"]
    for p in punches:
        # Evita quebrar CSV com vírgula no user agent
        ua = (p.user_agent or "").replace(",", " ")
        lines.append(
            f"{p.id},{p.ts_utc.isoformat()},{p.kind},{p.lat or ''},{p.lon or ''},{p.ip or ''},{ua},{p.photo_path or ''},{p.img_hash or ''}"
        )

    csv_text = "\n".join(lines) + "\n"
    resp = make_response(csv_text)
    resp.headers["Content-Type"] = "text/csv; charset=utf-8"
    resp.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


@bp.get("/health")
def health():
    return jsonify({"ok": True, "ts": datetime.now(timezone.utc).isoformat()})


@bp.post("/punch")
def punch():
    # Se exigir login e o PSA estiver com flask_login, bloqueia aqui
    if _require_login():
        if not login_required or not current_user or not getattr(current_user, "is_authenticated", False):
            return jsonify({"ok": False, "error": "LOGIN_REQUIRED"}), 401

    data = request.get_json(silent=True) or {}
    kind = (data.get("kind") or "").strip().lower()
    if kind not in {"entrada", "saida", "pausa", "retorno"}:
        return jsonify({"ok": False, "error": "INVALID_KIND"}), 400

    # Geolocalização (opcional)
    lat, lon, acc = parse_geo(data.get("geo"))
    if _require_geo():
        if lat is None or lon is None:
            return jsonify({"ok": False, "error": "GEO_REQUIRED"}), 400
        if not geo_within_radius_m(lat, lon, acc_m=acc):
            return jsonify({"ok": False, "error": "OUT_OF_GEOFENCE"}), 403

    # Foto obrigatória (industrial-ish, mas sem complicar)
    img_b64 = (data.get("image_base64") or "").strip()
    if not img_b64:
        return jsonify({"ok": False, "error": "IMAGE_REQUIRED"}), 400

    # Identidade: user_id (modo login) OU device_id (modo individual)
    user_id = None
    device_id = request.cookies.get("mydot_device_id")

    if _require_login() and current_user and getattr(current_user, "is_authenticated", False):
        user_id = getattr(current_user, "id", None)

    if not user_id:
        if not device_id:
            # cria um novo device_id e retorna no response
            device_id = str(uuid.uuid4())

    # Salva imagem em arquivo
    upload_dir = ensure_upload_dir()
    photo_relpath, img_hash = save_base64_image_jpeg(img_b64, upload_dir)

    # Salva no banco
    punch = MyDotPunch(
        user_id=user_id,
        device_id=device_id,
        kind=kind,
        ts_utc=datetime.now(timezone.utc),
        lat=lat,
        lon=lon,
        acc_m=acc,
        ip=request.headers.get("X-Forwarded-For", request.remote_addr),
        user_agent=request.headers.get("User-Agent"),
        photo_path=photo_relpath,
        img_hash=img_hash,
    )
    db.session.add(punch)
    db.session.commit()

    resp = make_response(jsonify({"ok": True, "id": punch.id, "ts_utc": punch.ts_utc.isoformat()}))

    # garante cookie no modo individual
    if not user_id:
        resp.set_cookie("mydot_device_id", device_id, max_age=60*60*24*365, samesite="Lax", secure=True)

    return resp

@bp.route("/config", methods=["GET", "POST"])
def config():

    device_id = get_or_set_device_id()

    cfg = MyDotConfig.query.filter_by(device_id=device_id).first()

    if not cfg:
        cfg = MyDotConfig(device_id=device_id)

    if request.method == "POST":

        cfg.daily_expected_minutes = int(request.form["daily"])
        cfg.min_lunch_minutes = int(request.form["lunch"])
        cfg.initial_balance_minutes = int(request.form["balance"])

        db.session.add(cfg)
        db.session.commit()

    return render_template("mydot/config.html", cfg=cfg)

@bp.get("/consultar")
def consultar_redirect():
    return redirect(url_for("mydot.history"))


@bp.get("/registrar")
def registrar_redirect():
    # por enquanto registrar = home ou uma página específica depois
    return redirect(url_for("mydot.home"))