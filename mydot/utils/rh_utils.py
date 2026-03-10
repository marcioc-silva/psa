from datetime import datetime, timedelta


def minutos_entre(inicio, fim):
    if not inicio or not fim:
        return 0
    return int((fim - inicio).total_seconds() // 60)


def calcular_saldo_diario(minutos_trabalhados, jornada_padrao_minutos):
    return minutos_trabalhados - jornada_padrao_minutos


def calcular_saldo_geral(saldo_inicial_minutos, soma_saldos_diarios):
    return saldo_inicial_minutos + soma_saldos_diarios


def verificar_regras_ouro(registro_atual, registro_anterior, config_rh):
    """
    registro_atual e registro_anterior devem ser objetos com atributos datetime.
    Esperado:
      registro_atual.entrada
      registro_atual.saida
      registro_atual.inicio_refeicao
      registro_atual.fim_refeicao
      registro_anterior.saida
    """
    notificacoes = []

    # 1) Refeição mínima
    if registro_atual.inicio_refeicao and registro_atual.fim_refeicao:
        refeicao_minutos = minutos_entre(registro_atual.inicio_refeicao, registro_atual.fim_refeicao)
        if (
            config_rh.notificar_refeicao_invalida
            and refeicao_minutos < config_rh.refeicao_minima_minutos
        ):
            notificacoes.append(
                f"Intervalo de refeição inferior a {config_rh.refeicao_minima_minutos} minutos."
            )

    # 2) Interjornada mínima
    if registro_anterior and registro_anterior.saida and registro_atual.entrada:
        horas_interjornada = (registro_atual.entrada - registro_anterior.saida).total_seconds() / 3600
        if (
            config_rh.notificar_interjornada_invalida
            and horas_interjornada < config_rh.interjornada_minima_horas
        ):
            notificacoes.append(
                f"Interjornada inferior a {config_rh.interjornada_minima_horas} horas."
            )

    # 3) Jornada máxima diária
    if registro_atual.entrada and registro_atual.saida:
        jornada_minutos = minutos_entre(registro_atual.entrada, registro_atual.saida)

        if registro_atual.inicio_refeicao and registro_atual.fim_refeicao:
            jornada_minutos -= minutos_entre(registro_atual.inicio_refeicao, registro_atual.fim_refeicao)

        if (
            config_rh.notificar_jornada_excedida
            and jornada_minutos > (config_rh.jornada_maxima_diaria_horas * 60)
        ):
            notificacoes.append(
                f"Jornada diária superior a {config_rh.jornada_maxima_diaria_horas} horas."
            )

    return notificacoes