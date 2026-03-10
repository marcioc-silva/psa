"""
Central de exportação dos models da aplicação.

Qualquer model que precise ser importado como:
    from app.models import AlgumModel

deve ser registrado aqui.
"""

# Models do módulo MyDot
from .ponto import ConfiguracaoRH, ConfiguracaoAparencia

# Lista explícita de exportação
__all__ = [
    "ConfiguracaoRH",
    "ConfiguracaoAparencia",
]