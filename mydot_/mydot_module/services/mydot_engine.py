from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Tuple

# Ajuste conforme seus kinds reais
KIND_IN = {"entrada", "in"}
KIND_OUT = {"saida", "out"}
KIND_BREAK_START = {"pausa", "break_start"}
KIND_BREAK_END = {"retorno", "break_end"}


# ----------------------------
# Estruturas de saída (limpas)
# ----------------------------

@dataclass
class RuleFlag:
    code: str                 # ex: "LUNCH_TOO_SHORT"
    level: str                # "info" | "warn" | "block"
    message: str


@dataclass
class DaySummary:
    day: date
    first_in: Optional[datetime]
    last_out: Optional[datetime]
    worked: timedelta         # total trabalhado (já descontando pausas)
    breaks: timedelta         # total pausas
    span: timedelta           # primeira entrada -> última saída (se existir)
    expected: timedelta       # esperado no dia (config)
    delta: timedelta          # worked - expected
    flags: List[RuleFlag]


@dataclass
class EngineResult:
    days: List[DaySummary]
    total_worked: timedelta
    total_expected: timedelta
    total_delta: timedelta
    flags: List[RuleFlag]     # flags “globais” (ex: semana estourada, etc)


# ----------------------------
# Helpers
# ----------------------------

def _td(minutes: int) -> timedelta:
    return timedelta(minutes=int(minutes))


def _fmt_td(td: timedelta) -> str:
    # formata -01:30 / 08:05
    sign = "-" if td.total_seconds() < 0 else ""
    s = abs(int(td.total_seconds()))
    hh = s // 3600
    mm = (s % 3600) // 60
    return f"{sign}{hh:02d}:{mm:02d}"


def _is_kind(kind: str, bag: set[str]) -> bool:
    return (kind or "").strip().lower() in bag


# ----------------------------
# Núcleo: construir sessões
# ----------------------------

@dataclass
class PunchLike:
    # Para não acoplar ao SQLAlchemy: basta ter .kind e .ts_local
    kind: str
    ts_local: datetime
    id: Optional[int] = None


def normalize_punches(punches: List[object]) -> List[PunchLike]:
    """
    Aceita lista de objetos SQLAlchemy (MyDotPunch) ou dicts e devolve PunchLike.
    Espera campos:
      - kind
      - ts_local (datetime)
      - id (opcional)
    """
    out: List[PunchLike] = []
    for p in punches:
        if isinstance(p, dict):
            out.append(PunchLike(
                id=p.get("id"),
                kind=p.get("kind"),
                ts_local=p.get("ts_local"),
            ))
        else:
            out.append(PunchLike(
                id=getattr(p, "id", None),
                kind=getattr(p, "kind", None),
                ts_local=getattr(p, "ts_local", None),
            ))
    # ordena por horário
    out.sort(key=lambda x: x.ts_local)
    return out


def group_by_day(punches: List[PunchLike]) -> Dict[date, List[PunchLike]]:
    days: Dict[date, List[PunchLike]] = {}
    for p in punches:
        d = p.ts_local.date()
        days.setdefault(d, []).append(p)
    return days


def build_work_break_timeline(day_punches: List[PunchLike]) -> Tuple[
    Optional[datetime], Optional[datetime], timedelta, timedelta, timedelta, List[RuleFlag]
]:
    """
    Constrói:
    - first_in / last_out
    - worked / breaks / span
    - flags de inconsistência (ex: duas entradas seguidas)
    """

    flags: List[RuleFlag] = []

    if not day_punches:
        return None, None, timedelta(0), timedelta(0), timedelta(0), flags

    first_in: Optional[datetime] = None
    last_out: Optional[datetime] = None

    worked = timedelta(0)
    breaks = timedelta(0)

    # Máquina de estados simples
    state = "idle"  # idle | working | break

    t_work_start: Optional[datetime] = None
    t_break_start: Optional[datetime] = None

    for p in day_punches:
        kind = (p.kind or "").lower().strip()
        t = p.ts_local

        if _is_kind(kind, KIND_IN):
            if state == "idle":
                state = "working"
                t_work_start = t
                if first_in is None:
                    first_in = t
            elif state == "working":
                flags.append(RuleFlag("DOUBLE_IN", "warn", "Duas entradas seguidas no mesmo dia."))
            elif state == "break":
                # voltou do almoço sem marcar retorno? trata como retorno implícito
                if t_break_start:
                    breaks += (t - t_break_start)
                state = "working"
                t_break_start = None
                t_work_start = t

        elif _is_kind(kind, KIND_OUT):
            if state == "working":
                if t_work_start:
                    worked += (t - t_work_start)
                state = "idle"
                t_work_start = None
                last_out = t
            elif state == "idle":
                flags.append(RuleFlag("OUT_WITHOUT_IN", "warn", "Saída sem entrada no mesmo dia."))
                last_out = t
            elif state == "break":
                # saiu durante pausa: fecha pausa e dia
                if t_break_start:
                    breaks += (t - t_break_start)
                state = "idle"
                t_break_start = None
                last_out = t

        elif _is_kind(kind, KIND_BREAK_START):
            if state == "working":
                # fecha bloco de trabalho e abre pausa
                if t_work_start:
                    worked += (t - t_work_start)
                state = "break"
                t_break_start = t
                t_work_start = None
            elif state == "break":
                flags.append(RuleFlag("DOUBLE_BREAK", "warn", "Duas pausas seguidas."))
            else:
                flags.append(RuleFlag("BREAK_WITHOUT_IN", "warn", "Pausa sem estar em trabalho."))

        elif _is_kind(kind, KIND_BREAK_END):
            if state == "break":
                if t_break_start:
                    breaks += (t - t_break_start)
                state = "working"
                t_break_start = None
                t_work_start = t
            else:
                flags.append(RuleFlag("RETURN_WITHOUT_BREAK", "warn", "Retorno sem pausa."))

        else:
            flags.append(RuleFlag("UNKNOWN_KIND", "info", f"Tipo desconhecido: {p.kind!r}"))

    # se terminou em working, não fecha automaticamente (pra não inventar hora de saída)
    # se terminou em break, também não fecha (pra não inventar retorno)
    span = timedelta(0)
    if first_in and last_out and last_out > first_in:
        span = last_out - first_in

    return first_in, last_out, worked, breaks, span, flags


# ----------------------------
# Regras de RH (configuráveis)
# ----------------------------

@dataclass
class RhRules:
    # valores em minutos (pra ficar fácil de salvar no config)
    daily_expected_minutes: int = 480       # 8h
    min_lunch_minutes: int = 60             # almoço mínimo
    max_daily_work_minutes: int = 600       # ex: 10h trabalhadas
    max_continuous_work_minutes: int = 360  # ex: 6h sem pausa (opcional)
    require_lunch_if_worked_over_minutes: int = 360  # se trabalhou >6h, exige almoço mínimo


def apply_rules(
    first_in: Optional[datetime],
    last_out: Optional[datetime],
    worked: timedelta,
    breaks: timedelta,
    span: timedelta,
    base_flags: List[RuleFlag],
    rules: RhRules,
) -> List[RuleFlag]:
    flags = list(base_flags)

    expected = _td(rules.daily_expected_minutes)

    # Almoço mínimo (se trabalhou "muito", exige)
    if worked >= _td(rules.require_lunch_if_worked_over_minutes):
        if breaks < _td(rules.min_lunch_minutes):
            flags.append(RuleFlag(
                "LUNCH_TOO_SHORT", "warn",
                f"Pausa total menor que o mínimo ({rules.min_lunch_minutes} min)."
            ))

    # Limite diário
    if worked > _td(rules.max_daily_work_minutes):
        flags.append(RuleFlag(
            "DAILY_LIMIT_EXCEEDED", "warn",
            "Tempo trabalhado excedeu o limite diário."
        ))

    # Dia sem saída (opcional: aviso)
    if first_in and not last_out:
        flags.append(RuleFlag(
            "MISSING_OUT", "warn",
            "Dia com entrada mas sem saída registrada."
        ))

    # Dia sem entrada (opcional: aviso)
    if last_out and not first_in:
        flags.append(RuleFlag(
            "MISSING_IN", "warn",
            "Dia com saída mas sem entrada registrada."
        ))

    # Banco do dia (informativo)
    delta = worked - expected
    if delta.total_seconds() < 0:
        flags.append(RuleFlag(
            "NEGATIVE_DAY_BALANCE", "info",
            f"Saldo do dia negativo ({_fmt_td(delta)})."
        ))

    return flags


# ----------------------------
# Função principal do engine
# ----------------------------

def compute(
    punches: List[object],
    rules: Optional[RhRules] = None,
) -> EngineResult:
    rules = rules or RhRules()

    norm = normalize_punches(punches)
    by_day = group_by_day(norm)

    days_out: List[DaySummary] = []
    total_worked = timedelta(0)
    total_expected = timedelta(0)

    for d in sorted(by_day.keys()):
        first_in, last_out, worked, breaks, span, base_flags = build_work_break_timeline(by_day[d])
        flags = apply_rules(first_in, last_out, worked, breaks, span, base_flags, rules)

        expected = _td(rules.daily_expected_minutes)
        delta = worked - expected

        days_out.append(DaySummary(
            day=d,
            first_in=first_in,
            last_out=last_out,
            worked=worked,
            breaks=breaks,
            span=span,
            expected=expected,
            delta=delta,
            flags=flags,
        ))

        total_worked += worked
        total_expected += expected

    total_delta = total_worked - total_expected

    # flags globais (exemplo simples)
    global_flags: List[RuleFlag] = []
    if total_delta.total_seconds() < 0:
        global_flags.append(RuleFlag("NEGATIVE_TOTAL_BALANCE", "info", "Saldo total está negativo."))

    return EngineResult(
        days=days_out,
        total_worked=total_worked,
        total_expected=total_expected,
        total_delta=total_delta,
        flags=global_flags,
    )