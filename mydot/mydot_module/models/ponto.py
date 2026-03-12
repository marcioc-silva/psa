from app import db
from datetime import datetime, timezone


class MyDotPunch(db.Model):
    __bind_key__ = "mydot"
    __tablename__ = "mydot_punch"

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(64), index=True, nullable=True)
    kind = db.Column(db.String(10), nullable=False)
    mydot_colaborador_id = db.Column(db.Integer, nullable=False, index=True)

    ts_utc = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        index=True,
        default=lambda: datetime.now(timezone.utc)
    )

    @property
    def ts_local(self):
        return self.ts_utc


class ConfiguracaoRH(db.Model):
    __bind_key__ = "mydot"
    __tablename__ = "configuracoes_rh"

    id = db.Column(db.Integer, primary_key=True)

    # Regras de ouro
    refeicao_minima_minutos = db.Column(db.Integer, default=60, nullable=False)
    interjornada_minima_horas = db.Column(db.Integer, default=11, nullable=False)
    jornada_maxima_diaria_horas = db.Column(db.Integer, default=10, nullable=False)

    # Jornada padrão
    jornada_padrao_minutos = db.Column(db.Integer, default=480, nullable=False)  # 8h = 480 min

    # Banco de horas
    saldo_inicial_minutos = db.Column(db.Integer, default=0, nullable=False)
    saldo_atual_minutos = db.Column(db.Integer, default=0, nullable=False)

    # Tipo de escala
    # opções: "5x1_5x2", "6x2"
    tipo_escala = db.Column(db.String(20), default="5x1_5x2", nullable=False)

    # Escala 5/1 alternado com 5/2
    usar_domingo_folga_fixa = db.Column(db.Boolean, default=True, nullable=False)
    usar_sabado_alternado = db.Column(db.Boolean, default=True, nullable=False)

    # Escala 6/2 dinâmica
    folga_dinamica_ativa = db.Column(db.Boolean, default=False, nullable=False)

    # Notificações
    notificar_refeicao_invalida = db.Column(db.Boolean, default=True, nullable=False)
    notificar_interjornada_invalida = db.Column(db.Boolean, default=True, nullable=False)
    notificar_jornada_excedida = db.Column(db.Boolean, default=True, nullable=False)

    # Auditoria
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<ConfiguracaoRH {self.id} - {self.tipo_escala}>"


class ConfiguracaoAparencia(db.Model):
    __bind_key__ = "mydot"
    __tablename__ = "configuracoes_aparencia"

    id = db.Column(db.Integer, primary_key=True)

    nome_sistema = db.Column(db.String(100), default="MyDot", nullable=False)
    logo_url = db.Column(db.String(255), nullable=True)

    cor_primaria = db.Column(db.String(20), default="#0d6efd", nullable=False)
    cor_secundaria = db.Column(db.String(20), default="#6c757d", nullable=False)
    cor_fundo = db.Column(db.String(20), default="#f8f9fa", nullable=False)
    cor_texto = db.Column(db.String(20), default="#212529", nullable=False)

    tema = db.Column(db.String(20), default="claro", nullable=False)
    mensagem_boas_vindas = db.Column(db.String(255), default="Bem-vindo ao sistema", nullable=True)
    favicon_url = db.Column(db.String(255), nullable=True)

    criado_em = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<ConfiguracaoAparencia {self.nome_sistema}>"


class MyDotBancoHoras(db.Model):
    __bind_key__ = "mydot"
    __tablename__ = "mydot_banco_horas"

    id = db.Column(db.Integer, primary_key=True)
    mydot_colaborador_id = db.Column(db.Integer, nullable=False, index=True)
    data_referencia = db.Column(db.Date, nullable=False, index=True)

    tipo_dia = db.Column(db.String(30), nullable=False, default="trabalhado")
    jornada_prevista_minutos = db.Column(db.Integer, nullable=False, default=0)
    minutos_trabalhados = db.Column(db.Integer, nullable=False, default=0)
    saldo_dia_minutos = db.Column(db.Integer, nullable=False, default=0)
    saldo_acumulado_minutos = db.Column(db.Integer, nullable=False, default=0)

    entrada_1 = db.Column(db.DateTime, nullable=True)
    saida_1 = db.Column(db.DateTime, nullable=True)
    entrada_2 = db.Column(db.DateTime, nullable=True)
    saida_2 = db.Column(db.DateTime, nullable=True)

    alerta_refeicao = db.Column(db.Boolean, default=False, nullable=False)
    alerta_interjornada = db.Column(db.Boolean, default=False, nullable=False)
    alerta_jornada_excedida = db.Column(db.Boolean, default=False, nullable=False)

    observacoes = db.Column(db.String(255), nullable=True)

    criado_em = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<MyDotBancoHoras colaborador={self.mydot_colaborador_id} data={self.data_referencia}>"


class MyDotLancamentoBancoHoras(db.Model):
    __bind_key__ = "mydot"
    __tablename__ = "mydot_lancamentos_banco_horas"

    id = db.Column(db.Integer, primary_key=True)
    mydot_colaborador_id = db.Column(db.Integer, nullable=False, index=True)
    data_referencia = db.Column(db.Date, nullable=False, index=True)
    tipo = db.Column(db.String(30), nullable=False, default="folga_banco_horas")
    observacao = db.Column(db.String(255), nullable=True)

    criado_em = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<MyDotLancamentoBancoHoras colaborador={self.mydot_colaborador_id} data={self.data_referencia} tipo={self.tipo}>"