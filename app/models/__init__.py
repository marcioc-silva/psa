"""
Pacote de Models da aplicação.

Regras aqui:
- NÃO mexer em sys.path
- NÃO importar Flask
- Apenas organizar/exportar modelos SQLAlchemy
"""

from __future__ import annotations

import importlib
from typing import Optional, Type

# Reexport do db (opcional, mas útil)
from app import db  # noqa: F401


def _resolve_user_model() -> Optional[Type]:
    """
    Resolve o model User sem quebrar o deploy.
    Procura por User em módulos comuns dentro de app.models.
    Ajuste a lista se seus arquivos tiverem outro nome.
    """
    candidates = [
        "app.models.user",      # app/models/user.py
        "app.models.usuarios",  # app/models/usuarios.py
        "app.models.usuario",   # app/models/usuario.py
        "app.models.auth",      # app/models/auth.py
    ]

    for module_name in candidates:
        try:
            mod = importlib.import_module(module_name)
            if hasattr(mod, "User"):
                return getattr(mod, "User")
        except Exception:
            continue

    return None


# Exporta User se encontrado (senão fica None)
User = _resolve_user_model()  # type: ignore


__all__ = [
    "db",
    "User",
]
