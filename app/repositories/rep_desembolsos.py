"""
Repositorio de desembolsos (KPIs del dashboard).

Fuente: fagcuentacredito (datamart de cartera). Cada crédito tiene su
fechadesembolsocredito real y montocapitaldesembolsado. El parámetro
`periodomes` (yyyymm) se interpreta como el MES de la fecha de desembolso;
el acumulado anual usa el año de ese mismo periodo.
"""
from sqlalchemy.orm import Session
from sqlalchemy import text


def _yyyy_mm(periodomes: int) -> tuple[str, str]:
    """Convierte 202506 -> ('2025', '202506')."""
    p = str(periodomes)
    return p[:4], p


def total_mes(db: Session, periodomes: int):
    """Volumen, nro de créditos y ticket promedio desembolsados en el mes."""
    return db.execute(text("""
        SELECT COUNT(*) AS n_creditos,
               COALESCE(SUM(montocapitaldesembolsado), 0) AS volumen,
               COALESCE(AVG(montocapitaldesembolsado), 0) AS ticket_promedio
        FROM fagcuentacredito
        WHERE montocapitaldesembolsado > 0
          AND TO_CHAR(fechadesembolsocredito, 'YYYYMM') = :ym
    """), {"ym": str(periodomes)}).fetchone()


def total_anual(db: Session, anio: str):
    """Volumen y nro de créditos desembolsados acumulado en el año."""
    return db.execute(text("""
        SELECT COUNT(*) AS n_creditos,
               COALESCE(SUM(montocapitaldesembolsado), 0) AS volumen,
               COALESCE(AVG(montocapitaldesembolsado), 0) AS ticket_promedio
        FROM fagcuentacredito
        WHERE montocapitaldesembolsado > 0
          AND TO_CHAR(fechadesembolsocredito, 'YYYY') = :anio
    """), {"anio": anio}).fetchall()  # fetchall por consistencia; será 1 fila


def por_oficina(db: Session, periodomes: int):
    """Desembolsos del mes agrupados por agencia (oficina) y su zona comercial."""
    return db.execute(text("""
        SELECT ag.codagencia, ag.desagencia,
               ag.codzonacomercial, ag.deszonacomercial,
               COUNT(*) AS n_creditos,
               COALESCE(SUM(f.montocapitaldesembolsado), 0) AS volumen
        FROM fagcuentacredito f
        JOIN dagencia ag ON ag.pkagencia = f.pkagencia
        WHERE f.montocapitaldesembolsado > 0
          AND TO_CHAR(f.fechadesembolsocredito, 'YYYYMM') = :ym
        GROUP BY ag.codagencia, ag.desagencia, ag.codzonacomercial, ag.deszonacomercial
        ORDER BY volumen DESC
    """), {"ym": str(periodomes)}).fetchall()


def por_zona(db: Session, periodomes: int):
    """Desembolsos del mes agrupados por zona comercial."""
    return db.execute(text("""
        SELECT ag.codzonacomercial, ag.deszonacomercial,
               COUNT(*) AS n_creditos,
               COALESCE(SUM(f.montocapitaldesembolsado), 0) AS volumen
        FROM fagcuentacredito f
        JOIN dagencia ag ON ag.pkagencia = f.pkagencia
        WHERE f.montocapitaldesembolsado > 0
          AND TO_CHAR(f.fechadesembolsocredito, 'YYYYMM') = :ym
        GROUP BY ag.codzonacomercial, ag.deszonacomercial
        ORDER BY volumen DESC
    """), {"ym": str(periodomes)}).fetchall()
