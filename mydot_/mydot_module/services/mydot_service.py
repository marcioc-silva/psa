from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta
from flask import request, Response

from mydot.mydot_module.models.ponto import MyDotPunch


def get_or_set_device_id(resp: Response) -> str:
    device_id = request.cookies.get("mydot_device_id")
    if not device_id:
        device_id = str(uuid.uuid4())
        # secure=True exige HTTPS (ok no Render)
        resp.set_cookie(
            "mydot_device_id",
            device_id,
            max_age=60 * 60 * 24 * 365,
            samesite="Lax",
            secure=True
        )
    return device_id


def decide_kind(device_id: str):
    last = (
        MyDotPunch.query
        .filter_by(device_id=device_id)
        .order_by(MyDotPunch.ts_utc.desc())
        .first()
    )

    if not last:
        return "entrada", "Entrada Jornada"

    diff = datetime.utcnow() - last.ts_utc

    # nova jornada após 11 horas
    if diff > timedelta(hours=11):
        return "entrada", "Entrada Jornada"

    if last.kind == "entrada":
        return "saida", "Saída"
    else:
        return "entrada", "Entrada"