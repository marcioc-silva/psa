from __future__ import annotations

from flask import Blueprint, render_template, abort, request
from flask_login import login_required, current_user

bp = Blueprint("manual", __name__, url_prefix="/manual")

# Conteúdo centralizado aqui (simples de manter).
# Se quiser, depois migramos isso pra arquivos .md ou banco.
MODULES = [
    {
        "id": 1,
        "title": "Boas-vindas e visão geral",
        "duration": "3–5 min",
        "audience": "Todos",
        "summary": "Entenda o objetivo do sistema, o fluxo e o que cada área resolve.",
        "sections": [
            {
                "h": "O que é o Controle PSA",
                "p": [
                    "O Controle PSA organiza a conferência de UDs, rastreia divergências e transforma o processo em indicadores de gestão (IRA, pendências, Pareto, vencimento).",
                    "A ideia é simples: reduzir erro, aumentar acuracidade e facilitar tomada de decisão."
                ]
            },
            {
                "h": "Fluxo geral (em 60 segundos)",
                "p": [
                    "1) Importa SAP → 2) Sistema organiza por PSA/Importação → 3) Conferência/Scanner → 4) Divergências → 5) Dashboard/Reportes."
                        "Obrservação importante: Unidade de depósito nunca deve estar vazio."
                ]
            },
        ],
        "checklist": [
            "Sei o objetivo do sistema",
            "Entendi o fluxo básico",
            "Sei onde ver indicadores e divergências",
        ],
    },
    {
        "id": 2,
        "title": "Navegação e atalhos",
        "duration": "4–6 min",
        "audience": "Todos",
        "summary": "Aprenda a se orientar (desktop e mobile) e achar tudo sem se perder.",
        "sections": [
            {
                "h": "Menu superior e páginas",
                "p": [
                    "Dashboard mostra visão gerencial.",
                    "Scanner/Conferência é onde o chão de fábrica acontece.",
                    "Relatórios trazem visão consolidada e filtros.",
                    "Configurações e Admin são para cadastros e e-mail."
                ]
            },
            {
                "h": "Mobile: o que muda",
                "p": [
                    "No celular, o menu vira o ícone ☰. Prefira filtros para reduzir o volume antes de analisar.",
                    "Evite rolar tabelas gigantes: filtre por PSA/Importação."
                ]
            },
        ],
        "checklist": [
            "Consigo ir do dashboard para divergências",
            "Consigo usar no celular sem quebrar layout",
        ],
    },
    {
        "id": 3,
        "title": "Filtros: PSA + Importação (sem cair em armadilhas)",
        "duration": "5–8 min",
        "audience": "Supervisão + Conferentes",
        "summary": "Como filtrar certo e evitar conclusões erradas.",
        "sections": [
            {
                "h": "Filtro PSA",
                "p": [
                    "Use PSA para analisar uma área específica (ex.: 143:PSAKRONES).",
                    "‘Todos os PSA’ é a visão geral — ótima para priorização."
                ]
            },
            {
                "h": "Filtro de Importação",
                "p": [
                    "Use Importação para enxergar o ‘snapshot’ daquele dia.",
                    "Importação é útil pra auditoria e comparações."
                ]
            },
            {
                "h": "Regra de ouro",
                "p": [
                    "Se os números parecerem ‘zerados’, 90% é filtro selecionado sem perceber.",
                    "Sempre valide o topo do dashboard antes de tirar conclusão."
                ]
            },
        ],
        "checklist": [
            "Sei quando usar PSA vs Importação",
            "Consigo limpar filtros e voltar ao geral",
        ],
    },
    {
        "id": 4,
        "title": "Indicadores (KPIs) e como interpretar",
        "duration": "6–10 min",
        "audience": "Liderança + Supervisão",
        "summary": "Leia os KPIs do painel como se fosse um painel Power BI.",
        "sections": [
            {
                "h": "KPI: Total / Conferidas / Pendentes",
                "p": [
                    "Total: universo atual do filtro.",
                    "Conferidas: o que já foi executado.",
                    "Pendentes: fila real de trabalho (prioridade operacional)."
                ]
            },
            {
                "h": "KPI: Qualidade / IRA",
                "p": [
                    "Indicador que resume eficiência do processo. Metas típicas: 98,5%+.",
                    "Quando cair, olhe Pareto e Divergências para achar as causas."
                ]
            },
        ],
        "checklist": [
            "Sei o que significa pendente vs divergente",
            "Sei o que olhar quando IRA cai",
        ],
    },
    {
        "id": 5,
        "title": "Divergências: triagem e ação",
        "duration": "6–12 min",
        "audience": "Conferentes + Supervisão",
        "summary": "Como tratar divergências com disciplina e rastreabilidade.",
        "sections": [
            {
                "h": "O que é divergência no sistema",
                "p": [
                    "Divergência indica diferença entre o esperado (SAP) e o conferido/real, ou inconsistências (lote/vencimento).",
                    "O objetivo é ser rápido no apontamento e claro na observação."
                ]
            },
            {
                "h": "Como agir (padrão)",
                "p": [
                    "1) Revalidar UD → 2) Confirmar material → 3) Conferir lote → 4) Conferir vencimento → 5) Registrar observação.",
                ]
            },
        ],
        "checklist": [
            "Sei o passo a passo da triagem",
            "Sei registrar observação de forma objetiva",
        ],
    },
    {
        "id": 6,
        "title": "Pareto e priorização (80/20 na prática)",
        "duration": "5–9 min",
        "audience": "Supervisão",
        "summary": "Transforme o gráfico em plano de ação.",
        "sections": [
            {
                "h": "Como usar o Pareto",
                "p": [
                    "Pareto mostra os itens que mais geram carga (UDs / divergências).",
                    "Use pra priorizar: atacar TOP 3 geralmente dá o maior ganho."
                ]
            },
            {
                "h": "Modelo de ação",
                "p": [
                    "Para cada TOP item: (Causa provável) → (Ação) → (Responsável) → (Prazo) → (Verificação)."
                ]
            },
        ],
        "checklist": [
            "Consigo transformar Pareto em ações",
        ],
    },
    {
        "id": 7,
        "title": "Reportes por e-mail + preview no navegador",
        "duration": "4–8 min",
        "audience": "Gestão",
        "summary": "Enviar resumo executivo bonito e com links úteis.",
        "sections": [
            {
                "h": "O que vai no reporte",
                "p": [
                    "KPIs do filtro, top pendências por PSA, top materiais com divergência, tabela de divergências recentes e links.",
                ]
            },
            {
                "h": "Dica de ouro",
                "p": [
                    "Reporte é o ‘resumo executivo’. O dashboard é o ‘drill down’. Use os dois."
                ]
            },
        ],
        "checklist": [
            "Consigo enviar e validar preview",
        ],
    },
    {
        "id": 8,
        "title": "Uso no celular sem quebrar layout",
        "duration": "3–6 min",
        "audience": "Todos",
        "summary": "Boas práticas para mobile e prevenção de erros.",
        "sections": [
            {
                "h": "Como usar melhor",
                "p": [
                    "Filtre antes (PSA/Importação).",
                    "Evite tabelas grandes: foque em cards e gráficos.",
                    "Se algo ‘sumir’, revise filtros."
                ]
            },
        ],
        "checklist": [
            "Consigo operar no celular com segurança",
        ],
    },
]


def _get_module(module_id: int):
    for m in MODULES:
        if m["id"] == module_id:
            return m
    return None


@bp.route("/")
@login_required
def index():
    return render_template("manual/index.html", modules=MODULES)


@bp.route("/modulo/<int:module_id>")
@login_required
def module_page(module_id: int):
    m = _get_module(module_id)
    if not m:
        abort(404)
    # Para o "Próximo módulo"
    next_id = module_id + 1 if _get_module(module_id + 1) else None
    prev_id = module_id - 1 if _get_module(module_id - 1) else None
    return render_template("manual/module.html", module=m, modules=MODULES, next_id=next_id, prev_id=prev_id)
