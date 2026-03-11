from collections import defaultdict
from datetime import datetime

from mydot.mydot_module.models.ponto import MyDotPunch


def minutos_entre(inicio, fim):
    if not inicio or not fim:
        return 0
    return int((fim - inicio).total_seconds() // 60)


def formatar_minutos(minutos):
    sinal = "-" if minutos < 0 else "+"
    minutos = abs(int(minutos))
    horas = minutos // 60
    mins = minutos % 60
    return f"{sinal}{horas:02d}:{mins:02d}"


def calcular_minutos_trabalhados(pontos_do_dia):
    """
    Soma pares entrada/saída na ordem:
    entrada, saída, entrada, saída...
    """
    total = 0

    for i in range(0, len(pontos_do_dia) - 1, 2):
        atual = pontos_do_dia[i]
        prox = pontos_do_dia[i + 1]

        if atual.kind == "entrada" and prox.kind == "saida":
            total += minutos_entre(atual.ts_utc, prox.ts_utc)

    return total


def extrair_batidas_do_dia(pontos_do_dia):
    entrada_1 = saida_1 = entrada_2 = saida_2 = None

    if len(pontos_do_dia) > 0:
        entrada_1 = pontos_do_dia[0].ts_utc if pontos_do_dia[0].kind == "entrada" else None
    if len(pontos_do_dia) > 1:
        saida_1 = pontos_do_dia[1].ts_utc if pontos_do_dia[1].kind == "saida" else None
    if len(pontos_do_dia) > 2:
        entrada_2 = pontos_do_dia[2].ts_utc if pontos_do_dia[2].kind == "entrada" else None
    if len(pontos_do_dia) > 3:
        saida_2 = pontos_do_dia[3].ts_utc if pontos_do_dia[3].kind == "saida" else None

    return entrada_1, saida_1, entrada_2, saida_2


def montar_resumo_banco_horas(config_rh):
    """
    Retorna:
    - linhas diárias
    - saldo total
    """
    registros = (
        MyDotPunch.query
        .order_by(MyDotPunch.ts_utc.asc())
        .all()
    )

    agrupado = defaultdict(list)

    for r in registros:
        if r.ts_utc:
            data_ref = r.ts_utc.date()
            agrupado[data_ref].append(r)

    linhas = []
    saldo_acumulado = config_rh.saldo_inicial_minutos or 0

    for data_ref in sorted(agrupado.keys()):
        pontos_do_dia = agrupado[data_ref]

        minutos_trabalhados = calcular_minutos_trabalhados(pontos_do_dia)
        jornada_prevista = config_rh.jornada_padrao_minutos or 0
        saldo_dia = minutos_trabalhados - jornada_prevista
        saldo_acumulado += saldo_dia

        entrada_1, saida_1, entrada_2, saida_2 = extrair_batidas_do_dia(pontos_do_dia)

        linhas.append({
            "data": data_ref.strftime("%d/%m/%Y"),
            "entrada_1": entrada_1.strftime("%H:%M") if entrada_1 else "-",
            "saida_1": saida_1.strftime("%H:%M") if saida_1 else "-",
            "entrada_2": entrada_2.strftime("%H:%M") if entrada_2 else "-",
            "saida_2": saida_2.strftime("%H:%M") if saida_2 else "-",
            "jornada_prevista_minutos": jornada_prevista,
            "minutos_trabalhados": minutos_trabalhados,
            "saldo_dia_minutos": saldo_dia,
            "saldo_acumulado_minutos": saldo_acumulado,
            "jornada_prevista_fmt": formatar_minutos(jornada_prevista).replace("+", ""),
            "minutos_trabalhados_fmt": formatar_minutos(minutos_trabalhados).replace("+", ""),
            "saldo_dia_fmt": formatar_minutos(saldo_dia),
            "saldo_acumulado_fmt": formatar_minutos(saldo_acumulado),
        })

    return {
        "linhas": linhas,
        "saldo_inicial_minutos": config_rh.saldo_inicial_minutos or 0,
        "saldo_inicial_fmt": formatar_minutos(config_rh.saldo_inicial_minutos or 0),
        "saldo_total_minutos": saldo_acumulado,
        "saldo_total_fmt": formatar_minutos(saldo_acumulado),
    }