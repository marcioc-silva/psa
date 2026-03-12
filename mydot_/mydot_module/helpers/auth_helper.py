from functools import wraps

from flask import session, redirect, url_for, flash

from mydot.mydot_module.models.auth import MyDotColaborador


def mydot_login_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if not session.get("mydot_colaborador_id"):
            flash("Faça login para acessar o MyDot.", "warning")
            return redirect(url_for("mydot.login"))
        return view_func(*args, **kwargs)
    return wrapped_view


def get_mydot_current_user():
    colaborador_id = session.get("mydot_colaborador_id")
    if not colaborador_id:
        return None

    try:
        return MyDotColaborador.query.get(int(colaborador_id))
    except Exception:
        return None


def inject_mydot_user():
    return {
        "mydot_current_user": get_mydot_current_user()
    }