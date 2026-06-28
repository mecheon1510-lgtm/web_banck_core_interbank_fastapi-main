"""
Repositorio de Recuperaciones / Mora (MPR Recuperación del Crédito).

R1 — Consulta de cartera en mora por banda.
R2 — Gestión de cobranza (registrar/listar acciones sobre créditos morosos).

Bandas de mora (del proceso, sobre diasatrasocredito):
  PREVENTIVA  : 1-6     (P01 — recordatorio)
  TEMPRANA    : 7-30    (P02 — SMS/llamada)
  TARDIA      : 31-120  (P03)
  JUDICIAL    : 121-180 (P04 — cobranza judicial)
  CASTIGO     : >180    (P06 — castigado)
"""
from sqlalchemy.orm import Session
from sqlalchemy import text

PERIODO = 202512

# Expresión SQL reutilizable que clasifica la banda por días de atraso.
BANDA_SQL = """
  CASE
    WHEN f.diasatrasocredito = 0 THEN 'AL_DIA'
    WHEN f.diasatrasocredito BETWEEN 1 AND 6 THEN 'PREVENTIVA'
    WHEN f.diasatrasocredito BETWEEN 7 AND 30 THEN 'TEMPRANA'
    WHEN f.diasatrasocredito BETWEEN 31 AND 120 THEN 'TARDIA'
    WHEN f.diasatrasocredito BETWEEN 121 AND 180 THEN 'JUDICIAL'
    ELSE 'CASTIGO'
  END
"""


def resumen_mora(db: Session, periodomes: int = PERIODO):
    """Conteo y saldo de cartera por banda de mora (para KPIs)."""
    return db.execute(text(f"""
        SELECT {BANDA_SQL} AS banda,
               COUNT(*) AS n_creditos,
               COALESCE(SUM(f.montosaldocapital), 0) AS saldo,
               COALESCE(SUM(f.montosaldovencido), 0) AS saldo_vencido
        FROM fagcuentacredito f
        WHERE f.periodomes = :per
        GROUP BY 1
        ORDER BY MIN(f.diasatrasocredito)
    """), {"per": periodomes}).fetchall()


def cartera_en_mora(db: Session, *, banda: str | None = None,
                    periodomes: int = PERIODO, limit: int = 100, offset: int = 0):
    """Lista de créditos morosos (filtrable por banda)."""
    where = ["f.periodomes = :per", "f.diasatrasocredito > 0"]
    params = {"per": periodomes, "limit": limit, "offset": offset}
    if banda:
        where.append(f"({BANDA_SQL}) = :banda")
        params["banda"] = banda.upper()
    return db.execute(text(f"""
        SELECT cc.codcuentacredito, cl.nomcliente, cl.codcliente,
               f.diasatrasocredito, f.montosaldocapital, f.montosaldovencido,
               f.flagjudicial, f.flagcastigado,
               cal.descalificacioncrediticia AS calificacion,
               {BANDA_SQL} AS banda,
               ag.codagencia, ag.desagencia
        FROM fagcuentacredito f
        JOIN dcuentacredito cc ON cc.pkcuentacredito = f.pkcuentacredito
        JOIN dcliente cl       ON cl.pkcliente = f.pkcliente
        LEFT JOIN dcalificacioncrediticia cal ON cal.pkcalificacioncrediticia = f.pkcalificacioncrediticiainterna
        LEFT JOIN dagencia ag  ON ag.pkagencia = f.pkagencia
        WHERE {' AND '.join(where)}
        ORDER BY f.diasatrasocredito DESC
        LIMIT :limit OFFSET :offset
    """), params).fetchall()


# ---------- R2: gestión de cobranza ----------

def tipos_gestion(db: Session):
    return db.execute(text(
        "SELECT pktipogestion, codtipogestion, destipogestion FROM dtipogestioncobranza ORDER BY pktipogestion"
    )).fetchall()


def _credito_por_cod(db: Session, codcuentacredito: str):
    return db.execute(text("""
        SELECT cc.pkcuentacredito, f.diasatrasocredito
        FROM dcuentacredito cc
        LEFT JOIN fagcuentacredito f ON f.pkcuentacredito = cc.pkcuentacredito AND f.periodomes = :per
        WHERE cc.codcuentacredito = :cod LIMIT 1
    """), {"cod": codcuentacredito, "per": PERIODO}).fetchone()


def _banda_de_dias(d: int) -> str:
    if d is None or d == 0: return "AL_DIA"
    if d <= 6: return "PREVENTIVA"
    if d <= 30: return "TEMPRANA"
    if d <= 120: return "TARDIA"
    if d <= 180: return "JUDICIAL"
    return "CASTIGO"


def registrar_gestion(db: Session, codcuentacredito: str, *, codtipogestion: str,
                      gestor: str, resultado: str = "",
                      compromiso_pago: str | None = None,
                      monto_comprometido: float | None = None) -> dict:
    cred = _credito_por_cod(db, codcuentacredito)
    if not cred:
        return {"error": "Crédito no encontrado"}
    pktipo = db.execute(text(
        "SELECT pktipogestion FROM dtipogestioncobranza WHERE codtipogestion=:c"),
        {"c": codtipogestion}).scalar()
    if not pktipo:
        return {"error": f"Tipo de gestión inválido: {codtipogestion}"}
    dias = cred.diasatrasocredito or 0
    row = db.execute(text("""
        INSERT INTO fgestioncobranza
            (pkcuentacredito, pktipogestion, fechagestion, diasatrasoalmomento, banda,
             gestor, resultado, compromisopago, montocomprometido, fecultactualizacion)
        VALUES (:pkcc, :pktipo, CURRENT_DATE, :dias, :banda,
                :gestor, :res, :comp, :monto, NOW())
        RETURNING pkgestion
    """), {"pkcc": cred.pkcuentacredito, "pktipo": pktipo, "dias": dias,
           "banda": _banda_de_dias(dias), "gestor": gestor, "res": resultado,
           "comp": compromiso_pago, "monto": monto_comprometido}).fetchone()
    db.commit()
    return {"pkgestion": row.pkgestion, "codcuentacredito": codcuentacredito,
            "banda": _banda_de_dias(dias), "dias_atraso": dias}


def listar_gestiones(db: Session, codcuentacredito: str):
    return db.execute(text("""
        SELECT g.pkgestion, g.fechagestion, t.destipogestion AS tipo,
               g.banda, g.gestor, g.resultado, g.compromisopago, g.montocomprometido,
               g.diasatrasoalmomento
        FROM fgestioncobranza g
        JOIN dcuentacredito cc ON cc.pkcuentacredito = g.pkcuentacredito
        JOIN dtipogestioncobranza t ON t.pktipogestion = g.pktipogestion
        WHERE cc.codcuentacredito = :cod
        ORDER BY g.fechagestion DESC, g.pkgestion DESC
    """), {"cod": codcuentacredito}).fetchall()


# ---------- R3: transiciones de estado de cobranza ----------

# Umbrales de días para pasar a cobranza judicial (MPR Recuperación):
#   Minorista 106 / No Minorista 121 / Refinanciado 76. Usamos 121 como regla general.
DIAS_JUDICIAL = 121
DIAS_CASTIGO = 180

# pkestadocredito (de destadocredito): 3=En Cobranza Judicial, 7=Castigado
ESTADO_JUDICIAL = 3
ESTADO_CASTIGADO = 7


def _credito_full(db: Session, codcuentacredito: str):
    return db.execute(text("""
        SELECT cc.pkcuentacredito, f.diasatrasocredito, f.flagjudicial, f.flagcastigado,
               f.pkestadocredito
        FROM dcuentacredito cc
        JOIN fagcuentacredito f ON f.pkcuentacredito = cc.pkcuentacredito AND f.periodomes = :per
        WHERE cc.codcuentacredito = :cod LIMIT 1
    """), {"cod": codcuentacredito, "per": PERIODO}).fetchone()


def pasar_a_judicial(db: Session, codcuentacredito: str, *, gestor: str,
                     forzar: bool = False) -> dict:
    """
    Transición a Cobranza Judicial (P04). Regla: >= DIAS_JUDICIAL días de atraso.
    Marca flagjudicial='S', fechaingresojudicial=hoy, estado=En Cobranza Judicial.
    Registra la gestión JUDI para trazabilidad.
    """
    cr = _credito_full(db, codcuentacredito)
    if not cr:
        return {"error": "Crédito no encontrado"}
    if (cr.flagjudicial or "N") == "S":
        return {"error": "El crédito ya está en cobranza judicial"}
    dias = cr.diasatrasocredito or 0
    if not forzar and dias < DIAS_JUDICIAL:
        return {"error": f"No cumple el umbral: {dias} días (requiere >= {DIAS_JUDICIAL})"}

    db.execute(text("""
        UPDATE fagcuentacredito
        SET flagjudicial='S', fechaingresojudicial=CURRENT_DATE,
            pkestadocredito=:est, fecultactualizacion=NOW()
        WHERE pkcuentacredito=:pk AND periodomes=:per
    """), {"est": ESTADO_JUDICIAL, "pk": cr.pkcuentacredito, "per": PERIODO})
    # gestión de trazabilidad
    pktipo = db.execute(text("SELECT pktipogestion FROM dtipogestioncobranza WHERE codtipogestion='JUDI'")).scalar()
    db.execute(text("""
        INSERT INTO fgestioncobranza
            (pkcuentacredito, pktipogestion, fechagestion, diasatrasoalmomento, banda,
             gestor, resultado, fecultactualizacion)
        VALUES (:pk, :t, CURRENT_DATE, :dias, 'JUDICIAL', :g, 'Derivado a cobranza judicial', NOW())
    """), {"pk": cr.pkcuentacredito, "t": pktipo, "dias": dias, "g": gestor})
    db.commit()
    return {"codcuentacredito": codcuentacredito, "estado": "En Cobranza Judicial",
            "dias_atraso": dias, "fecha_ingreso_judicial": "hoy"}


def castigar(db: Session, codcuentacredito: str, *, gestor: str,
             forzar: bool = False) -> dict:
    """
    Transición a Castigado (P06). Regla: > DIAS_CASTIGO días de atraso.
    Marca flagcastigado='S', estado=Castigado.
    """
    cr = _credito_full(db, codcuentacredito)
    if not cr:
        return {"error": "Crédito no encontrado"}
    if (cr.flagcastigado or "N") == "S":
        return {"error": "El crédito ya está castigado"}
    dias = cr.diasatrasocredito or 0
    if not forzar and dias <= DIAS_CASTIGO:
        return {"error": f"No cumple el umbral: {dias} días (requiere > {DIAS_CASTIGO})"}

    db.execute(text("""
        UPDATE fagcuentacredito
        SET flagcastigado='S', pkestadocredito=:est, fecultactualizacion=NOW()
        WHERE pkcuentacredito=:pk AND periodomes=:per
    """), {"est": ESTADO_CASTIGADO, "pk": cr.pkcuentacredito, "per": PERIODO})
    pktipo = db.execute(text("SELECT pktipogestion FROM dtipogestioncobranza WHERE codtipogestion='CART'")).scalar()
    db.execute(text("""
        INSERT INTO fgestioncobranza
            (pkcuentacredito, pktipogestion, fechagestion, diasatrasoalmomento, banda,
             gestor, resultado, fecultactualizacion)
        VALUES (:pk, :t, CURRENT_DATE, :dias, 'CASTIGO', :g, 'Crédito castigado contablemente', NOW())
    """), {"pk": cr.pkcuentacredito, "t": pktipo, "dias": dias, "g": gestor})
    db.commit()
    return {"codcuentacredito": codcuentacredito, "estado": "Castigado", "dias_atraso": dias}
