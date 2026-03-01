import sys
import os
from .material import MaterialPSA, HistoricoPSA
from .configuracao import ConfiguracaoSistema
from .usuario import Usuario

# Adiciona o diretório atual ao caminho de busca do Python
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from flask import Flask # ... e as outras importações que você já tem