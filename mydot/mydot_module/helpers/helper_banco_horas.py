from collections import defaultdict

from app import db
from mydot.mydot_module.models.ponto import (
    MyDotPunch,
    MyDotBancoHoras,
    MyDotLancamentoBancoHoras,
    ConfiguracaoRH,
)


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


def obter_config_rh():
    config = ConfiguracaoRH.query.first()
    if not config:
        config = ConfiguracaoRH()
        db.session.add(config)
        db.session.commit()
    return config


def calcular_alertas(config_rh, pontos_do_dia, minutos_trabalhados):
    alerta_refeicao = False
    alerta_interjornada = False
    alerta_jornada_excedida = False

    entrada_1, saida_1, entrada_2, saida_2 = extrair_batidas_do_dia(pontos_do_dia)

    if saida_1 and entrada_2:
        intervalo_refeicao = minutos_entre(saida_1, entrada_2)
        if intervalo_refeicao < config_rh.refeicao_minima_minutos:
            alerta_refeicao = True

    if minutos_trabalhados > (config_rh.jornada_maxima_diaria_horas * 60):
        alerta_jornada_excedida = True

    return alerta_refeicao, alerta_interjornada, alerta_jornada_excedida


def recalcular_banco_horas(colaborador_id):
    config_rh = obter_config_rh()

    registros = (
        MyDotPunch.query
        .filter(MyDotPunch.mydot_colaborador_id == colaborador_id)
        .order_by(MyDotPunch.ts_utc.asc())
        .all()
    )

    agrupado = defaultdict(list)
    for r in registros:
        if r.ts_utc:
            agrupado[r.ts_utc.date()].append(r)

    lancamentos = {
        item.data_referencia: item
        for item in MyDotLancamentoBancoHoras.query
        .filter(MyDotLancamentoBancoHoras.mydot_colaborador_id == colaborador_id)
        .all()
    }

    datas_com_ponto = set(agrupado.keys())
    datas_com_lancamento = set(lancamentos.keys())
    datas_processadas = sorted(datas_com_ponto | datas_com_lancamento)

    (
        MyDotBancoHoras.query
        .filter(MyDotBancoHoras.mydot_colaborador_id == colaborador_id)
        .delete()
    )
    db.session.commit()

    saldo_acumulado = config_rh.saldo_inicial_minutos or 0

    for data_ref in datas_processadas:
        pontos_do_dia = agrupado.get(data_ref, [])
        lancamento = lancamentos.get(data_ref)

        jornada_prevista = config_rh.jornada_padrao_minutos or 0
        tipo_dia = "trabalhado"
        minutos_trabalhados = 0

        entrada_1 = saida_1 = entrada_2 = saida_2 = None
        alerta_refeicao = False
        alerta_interjornada = False
        alerta_jornada_excedida = False
        observacoes = None

        if lancamento and lancamento.tipo == "banco_horas":
            tipo_dia = "banco_horas"
            minutos_trabalhados = 0
            saldo_dia = -jornada_prevista
            observacoes = lancamento.observacao

        elif pontos_do_dia:
            tipo_dia = "trabalhado"
            minutos_trabalhados = calcular_minutos_trabalhados(pontos_do_dia)
            saldo_dia = minutos_trabalhados - jornada_prevista

            entrada_1, saida_1, entrada_2, saida_2 = extrair_batidas_do_dia(pontos_do_dia)
            alerta_refeicao, alerta_interjornada, alerta_jornada_excedida = calcular_alertas(
                config_rh,
                pontos_do_dia,
                minutos_trabalhados,
            )

        else:
            tipo_dia = "folga"
            saldo_dia = 0

        saldo_acumulado += saldo_dia

        item = MyDotBancoHoras(
            mydot_colaborador_id=colaborador_id,
            data_referencia=data_ref,
            tipo_dia=tipo_dia,
            jornada_prevista_minutos=jornada_prevista,
            minutos_trabalhados=minutos_trabalhados,
            saldo_dia_minutos=saldo_dia,
            saldo_acumulado_minutos=saldo_acumulado,
            entrada_1=entrada_1,
            saida_1=saida_1,
            entrada_2=entrada_2,
            saida_2=saida_2,
            alerta_refeicao=alerta_refeicao,
            alerta_interjornada=alerta_interjornada,
            alerta_jornada_excedida=alerta_jornada_excedida,
            observacoes=observacoes,
        )
        db.session.add(item)

    db.session.commit()


def _montar_resumo_de_registros(registros, saldo_inicial_minutos):
    linhas = []

    for r in registros:
        linhas.append({
            "data": r.data_referencia.strftime("%d/%m/%Y") if r.data_referencia else "-",
            "tipo_dia": r.tipo_dia or "trabalhado",
            "entrada_1": r.entrada_1.strftime("%H:%M") if r.entrada_1 else "-",
            "saida_1": r.saida_1.strftime("%H:%M") if r.saida_1 else "-",
            "entrada_2": r.entrada_2.strftime("%H:%M") if r.entrada_2 else "-",
            "saida_2": r.saida_2.strftime("%H:%M") if r.saida_2 else "-",
            "jornada_prevista_minutos": r.jornada_prevista_minutos or 0,
            "minutos_trabalhados": r.minutos_trabalhados or 0,
            "saldo_dia_minutos": r.saldo_dia_minutos or 0,
            "saldo_acumulado_minutos": r.saldo_acumulado_minutos or 0,
            "jornada_prevista_fmt": formatar_minutos(r.jornada_prevista_minutos or 0).replace("+", ""),
            "minutos_trabalhados_fmt": formatar_minutos(r.minutos_trabalhados or 0).replace("+", ""),
            "saldo_dia_fmt": formatar_minutos(r.saldo_dia_minutos or 0),
            "saldo_acumulado_fmt": formatar_minutos(r.saldo_acumulado_minutos or 0),
        })

    saldo_total = linhas[-1]["saldo_acumulado_minutos"] if linhas else (saldo_inicial_minutos or 0)

    return {
        "linhas": linhas,
        "saldo_inicial_minutos": saldo_inicial_minutos or 0,
        "saldo_inicial_fmt": formatar_minutos(saldo_inicial_minutos or 0),
        "saldo_total_minutos": saldo_total,
        "saldo_total_fmt": formatar_minutos(saldo_total),
    }


def montar_resumo_banco_horas(config_rh, colaborador_id):
    """
    Gera o resumo já com os lançamentos de banco de horas
    impactando diretamente no saldo.
    """
    recalcular_banco_horas(colaborador_id)

    registros = (
        MyDotBancoHoras.query
        .filter(MyDotBancoHoras.mydot_colaborador_id == colaborador_id)
        .order_by(MyDotBancoHoras.data_referencia.asc())
        .all()
    )

    return _montar_resumo_de_registros(
        registros,
        config_rh.saldo_inicial_minutos or 0,
    )


def listar_banco_horas(colaborador_id):
    """
    Retorna o resumo consolidado do banco de horas
    já pronto para a tela.
    """
    config_rh = obter_config_rh()
    recalcular_banco_horas(colaborador_id)

    registros = (
        MyDotBancoHoras.query
        .filter(MyDotBancoHoras.mydot_colaborador_id == colaborador_id)
        .order_by(MyDotBancoHoras.data_referencia.asc())
        .all()
    )

    return _montar_resumo_de_registros(
        registros,
        config_rh.saldo_inicial_minutos or 0,
    )