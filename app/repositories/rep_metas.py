from sqlalchemy.orm import Session
from sqlalchemy import text

def get_productividad_asesores(db: Session, periodomes: int = 202512,
                                codagencia: str = None):
    # dasesor / fmetasasesor no tienen relación con agencia en este esquema,
    # por eso no se hace JOIN con dagencia ni se filtra por codagencia.
    sql = text("""
        SELECT
            a.codasesor,
            a.nomasesor,
            m.saldocolocaciones_real,
            m.saldocolocaciones_meta,
            m.nroclientes_real,
            m.nroclientes_meta,
            m.ratiomora_real
        FROM fmetasasesor m
        JOIN dasesor a ON a.pkasesor = m.pkasesor
        WHERE m.periodomes = :periodomes
        ORDER BY m.saldocolocaciones_real DESC
    """)
    return db.execute(sql, {"periodomes": periodomes}).fetchall()

def get_evolucion_historica(db: Session):
    sql = text("""
        SELECT
            m.periodomes,
            t.codtipocredito,
            m.saldocolocaciones_real,
            m.saldocolocaciones_meta,
            m.ratiomora_real
        FROM fmetatipocredito m
        JOIN dtipocredito t ON t.pktipocredito = m.pktipocredito
        ORDER BY m.periodomes, t.codtipocredito
    """)
    return db.execute(sql).fetchall()