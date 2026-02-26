from functools import wraps

from flask import abort
from flask_login import current_user


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not getattr(current_user, 'is_authenticated', False):
            abort(401)
        if not getattr(current_user, 'is_admin', False):
            abort(403)
        return fn(*args, **kwargs)

    return wrapper
