from sqlalchemy.orm import Session
from sqlalchemy import text

def get_kpis_periodo(db: Session, periodomes: int = 202512):
    sql = text("""
        SELECT
            COUNT(DISTINCT cc.pkcliente)            AS n_clientes,
            COUNT(f.pkcuentacredito)                AS n_creditos,
            SUM(f.montosaldocapital)                AS cartera_total,
            SUM(f.car_vig_capital)                  AS cartera_vigente,
            SUM(f.car_ven_capital)                  AS cartera_vencida,
            ROUND(
                SUM(f.car_ven_capital) /
                NULLIF(SUM(f.montosaldocapital),0) * 100, 4
            )                                       AS ratio_mora
        FROM fagcuentacredito f
        JOIN dcuentacredito cc ON cc.pkcuentacredito = f.pkcuentacredito
        WHERE f.periodomes = :periodomes
    """)
    return db.execute(sql, {"periodomes": periodomes}).fetchone()