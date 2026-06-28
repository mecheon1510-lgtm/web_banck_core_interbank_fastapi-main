from sqlalchemy.orm import Session
from sqlalchemy import text

def get_resumen_agencia(db: Session, codagencia: str, periododia: int = 20251231):
    """Saldo de ahorros agrupado por tipo de cuenta para una agencia."""
    sql = text("""
        SELECT
            tca.codtipocuentaahorro       AS tipo,
            COUNT(*)                      AS n_cuentas,
            SUM(f.montosaldocapitaltotal) AS saldo_total
        FROM fcuentaahorro f
        JOIN dcuentaahorro ca       ON ca.pkcuentaahorro = f.pkcuentaahorro
        JOIN dagencia ag            ON ag.pkagencia = f.pkagencia
        JOIN dtipocuentaahorro tca  ON tca.pktipocuentaahorro = f.pktipocuentaahorro
        WHERE ag.codagencia = :codagencia
          AND f.periododia = :periododia
        GROUP BY tca.codtipocuentaahorro
        ORDER BY saldo_total DESC
    """)
    return db.execute(sql, {
        "codagencia": codagencia,
        "periododia": periododia
    }).fetchall()

def get_cuentas_cliente(db: Session, codcliente: str, periododia: int = 20251231):
    """Cuentas de ahorro de un cliente con su saldo del período indicado."""
    sql = text("""
        SELECT
            ca.codcuentaahorro,
            cl.nomcliente,
            tca.codtipocuentaahorro       AS tipo_cuenta,
            f.montosaldocapitaltotal,
            f.montosaldointerestotal,
            f.tasaefectivaanual,
            ca.fechaaperturacuenta
        FROM dcuentaahorro ca
        JOIN dcliente cl            ON cl.pkcliente = ca.pkcliente
        LEFT JOIN fcuentaahorro f
               ON f.pkcuentaahorro = ca.pkcuentaahorro
              AND f.periododia = :periododia
        LEFT JOIN dtipocuentaahorro tca
               ON tca.pktipocuentaahorro = f.pktipocuentaahorro
        WHERE cl.codcliente = :codcliente
        ORDER BY f.montosaldocapitaltotal DESC NULLS LAST
    """)
    return db.execute(sql, {
        "codcliente": codcliente,
        "periododia": periododia
    }).fetchall()

def get_detalle(db: Session, codcuentaahorro: str, periododia: int = 20251231):
    """Detalle de una cuenta de ahorro con su saldo más reciente."""
    sql = text("""
        SELECT
            ca.codcuentaahorro,
            cl.nomcliente,
            cl.numerodocumentoidentidad,
            tca.codtipocuentaahorro       AS tipo_cuenta,
            ca.fechaaperturacuenta,
            f.montosaldocapitaltotal,
            f.montosaldointerestotal,
            f.tasaefectivaanual
        FROM dcuentaahorro ca
        JOIN dcliente cl            ON cl.pkcliente = ca.pkcliente
        LEFT JOIN fcuentaahorro f
               ON f.pkcuentaahorro = ca.pkcuentaahorro
              AND f.periododia = :periododia
        LEFT JOIN dtipocuentaahorro tca
               ON tca.pktipocuentaahorro = f.pktipocuentaahorro
        WHERE ca.codcuentaahorro = :cod
        LIMIT 1
    """)
    return db.execute(sql, {
        "cod": codcuentaahorro,
        "periododia": periododia
    }).fetchone()
