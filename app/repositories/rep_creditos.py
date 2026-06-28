from sqlalchemy.orm import Session
from sqlalchemy import text


def get_cartera_asesor(db: Session, pkasesor: int, periodomes: int = 202512):
    """Cartera activa de un asesor desde FAGCUENTACREDITO."""
    sql = text("""
        SELECT
            cc.codcuentacredito,
            cl.nomcliente,
            cl.numerodocumentoidentidad,
            f.montosaldocapital,
            f.diasatrasocredito,
            f.car_vig_capital,
            f.car_ven_capital,
            f.saldoprovisiones,
            cal.codcalificacioncrediticia AS calificacion
        FROM fagcuentacredito f
        JOIN dcuentacredito cc ON cc.pkcuentacredito = f.pkcuentacredito
        JOIN dcliente cl       ON cl.pkcliente = cc.pkcliente
        LEFT JOIN dcalificacioncrediticia cal
            ON cal.pkcalificacioncrediticia = f.pkcalificacioncrediticiainterna
        WHERE f.pkasesor = :pkasesor
          AND f.periodomes = :periodomes
        ORDER BY f.diasatrasocredito DESC
    """)
    return db.execute(sql, {
        "pkasesor": pkasesor,
        "periodomes": periodomes
    }).fetchall()

def get_detalle(db: Session, codcuentacredito: str):
    sql = text("""
        SELECT
            cc.codcuentacredito,
            cl.nomcliente,
            cl.numerodocumentoidentidad,
            s.montoaprobadocredito,
            s.nrocuotaaprobado,
            s.tasainterescompensatoria,
            s.fechaaprobacioncredito,
            f.montosaldocapital,
            f.montosaldointeres,
            f.diasatrasocredito,
            f.montosaldocliente
        FROM dcuentacredito cc
        JOIN dcliente cl ON cl.pkcliente = cc.pkcliente
        LEFT JOIN dsolicitud s ON s.pkcliente = cc.pkcliente
        LEFT JOIN fagcuentacredito f ON f.pkcuentacredito = cc.pkcuentacredito
        WHERE cc.codcuentacredito = :cod
        LIMIT 1
    """)
    return db.execute(sql, {"cod": codcuentacredito}).fetchone()

def get_cronograma(db: Session, codcuentacredito: str):
    sql = text("""
        SELECT
            p.nrocuota,
            p.fechavencimientopagocuota,
            p.montocuota,
            p.montocapitalprogramado,
            p.montointeresprogramado,
            p.montosaldo,
            p.codestadocuota
        FROM fplanpagomes p
        JOIN dcuentacredito cc ON cc.pkcuentacredito = p.pkcuentacredito
        WHERE cc.codcuentacredito = :cod
        ORDER BY p.nrocuota
    """)
    return db.execute(sql, {"cod": codcuentacredito}).fetchall()

def tiene_mala_calificacion(db: Session, pkcliente: int) -> bool:
    """
    True si el cliente tiene algún crédito con calificación Deficiente/Dudoso/Pérdida
    (cod 2/3/4). Se usa SOLO para PENALIZAR el pre-scoring; la decisión de elegibilidad
    (gate de sujeto de crédito) la toma svc_elegibilidad, que es la fuente de verdad.
    """
    sql = text("""
        SELECT COUNT(*) FROM fagcuentacredito f
        JOIN dcuentacredito cc ON cc.pkcuentacredito = f.pkcuentacredito
        JOIN dcalificacioncrediticia cal
            ON cal.pkcalificacioncrediticia = f.pkcalificacioncrediticiainterna
        WHERE cc.pkcliente = :pkcliente
          AND cal.codcalificacioncrediticia IN ('2','3','4')
          AND f.periodomes = 202512
    """)
    result = db.execute(sql, {"pkcliente": pkcliente}).scalar()
    return result > 0

# Mapeo de codtipocredito de dproducto (01/02/03) al código funcional (ME/PE/CO)
# que usa el backend (scoring, ruteo) y que el frontend envía.
_TIPO_PROD_A_FUNC = {"01": "ME", "02": "PE", "03": "CO"}
_SEGMENTO = {"ME": "EMPRESARIAL", "PE": "EMPRESARIAL", "CO": "CONSUMO"}


def get_productos_disponibles(db: Session):
    """
    Tipos de crédito disponibles (distintos) según dproducto, agrupables por segmento.
    Devuelve filas con: codtipocredito(01/02/03), destipocredito.
    """
    return db.execute(text("""
        SELECT DISTINCT codtipocredito, destipocredito
        FROM dproducto
        WHERE flagactivo = '1'
        ORDER BY codtipocredito
    """)).fetchall()


def map_tipo_func(cod_prod: str) -> str:
    """01->ME, 02->PE, 03->CO (código funcional que espera el backend)."""
    return _TIPO_PROD_A_FUNC.get((cod_prod or "").strip(), (cod_prod or "").strip())


def segmento_de(cod_func: str) -> str:
    """ME/PE -> EMPRESARIAL, CO -> CONSUMO."""
    return _SEGMENTO.get(cod_func, "OTRO")
