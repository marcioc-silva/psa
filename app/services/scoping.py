from flask_login import current_user
from app.models.material import MaterialPSA

def scoped_material_query():
    q = MaterialPSA.query

    # Se não estiver logado, não tenta acessar current_user.id
    if not current_user.is_authenticated:
        # Retorna uma query vazia (não vaza nada e evita erro)
        return q.filter(False)

    # Admin vê tudo, usuário comum vê só o dele
    if getattr(current_user, "is_admin", False):
        return q

    return q.filter(MaterialPSA.user_id == current_user.id)


def scoped_historico_query():
    q = HistoricoPSA.query
    if getattr(current_user, 'is_admin', False):
        return q
    return q.filter(HistoricoPSA.user_id == current_user.id)
