from __future__ import annotations

import os
import uuid
import base64
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Tuple, Optional

from flask import request, current_app, Response

# ---------- Device ID (modo individual) ----------

def get_or_set_device_id(resp: Response) -> str:
    device_id = request.cookies.get("mydot_device_id")
    if not device_id:
        device_id = str(uuid.uuid4())
        # secure=True exige HTTPS (recomendado). Em dev local, pode ajustar.
        resp.set_cookie("mydot_device_id", device_id, max_age=60*60*24*365, samesite="Lax", secure=True)
    return device_id


# ---------- Upload / Foto ----------

def ensure_upload_dir() -> Path:
    upload_dir = os.getenv("MYDOT_UPLOAD_DIR", "app/static/mydot/uploads")
    p = Path(upload_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p


def save_base64_image_jpeg(image_base64: str, upload_dir: Path) -> Tuple[str, str]:
    # aceita data URL ou base64 puro
    if image_base64.startswith("data:image"):
        header, b64 = image_base64.split(",", 1)
    else:
        b64 = image_base64

    raw = base64.b64decode(b64, validate=False)

    img_hash = hashlib.sha256(raw).hexdigest()

    filename = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_") + img_hash[:12] + ".jpg"
    path = upload_dir / filename
    path.write_bytes(raw)

    # caminho relativo a partir de app/static
    # upload_dir default: app/static/mydot/uploads => rel: mydot/uploads/<file>
    rel = str(path).replace("app/static/", "").replace("\\", "/")
    return rel, img_hash


# ---------- Geo ----------

def parse_geo(geo: Any) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    if not isinstance(geo, dict):
        return None, None, None
    try:
        lat = float(geo.get("lat")) if geo.get("lat") is not None else None
        lon = float(geo.get("lon")) if geo.get("lon") is not None else None
        acc = float(geo.get("acc_m")) if geo.get("acc_m") is not None else None
        return lat, lon, acc
    except Exception:
        return None, None, None


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    # Distância aproximada em metros
    from math import radians, sin, cos, sqrt, atan2

    R = 6371000.0
    p1 = radians(lat1)
    p2 = radians(lat2)
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = sin(dlat / 2) ** 2 + cos(p1) * cos(p2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c


def geo_within_radius_m(lat: float, lon: float, acc_m: Optional[float] = None) -> bool:
    # Se site não estiver configurado, não bloqueia (modo individual friendly)
    site_lat = os.getenv("MYDOT_SITE_LAT")
    site_lon = os.getenv("MYDOT_SITE_LON")
    if not site_lat or not site_lon:
        return True

    try:
        site_lat_f = float(site_lat)
        site_lon_f = float(site_lon)
    except Exception:
        return True

    radius_m = float(os.getenv("MYDOT_GEO_RADIUS_M", "200"))
    d = _haversine_m(lat, lon, site_lat_f, site_lon_f)

    # Se acc_m vier alto demais, trate como suspeito (industrial), mas no individual seja tolerante:
    # aqui só soma a precisão como “margem”.
    margin = float(acc_m) if acc_m else 0.0
    return d <= (radius_m + margin)
