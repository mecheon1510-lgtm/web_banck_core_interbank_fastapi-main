"""
Repositorio del Homebanking (portal del cliente).

Tablas: usuarios_homebanking (credenciales), foperaciones (movimientos),
dcuentacredito/fplanpagomes (créditos y cuotas del cliente).
"""
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text


def get_usuario(db: Session, username: str):
    return db.execute(text("""
        SELECT u.pkusuario, u.pkcliente, u.username, u.password_hash,
               u.activo, u.bloqueado, cl.codcliente, cl.nomcliente
        FROM usuarios_homebanking u
        JOIN dcliente cl ON cl.pkcliente = u.pkcliente
        WHERE LOWER(u.username) = LOWER(:u)
        LIMIT 1
    """), {"u": username}).fetchone()


def registrar_acceso(db: Session, pkusuario: int):
    db.execute(text("UPDATE usuarios_homebanking SET ultimo_acceso=NOW(), "
                    "intentos_fallidos=0 WHERE pkusuario=:pk"), {"pk": pkusuario})
    db.commit()


def movimientos(db: Session, pkcliente: int, limit: int = 50):
    """Historial de operaciones del cliente (desembolsos, pagos) por sus créditos."""
    return db.execute(text("""
        SELECT o.pkoperacion, o.codkardex, o.codtipkar,
               co.desconceptooperacion AS concepto,
               ca.descanaltransaccional AS canal,
               mp.desmediopago AS medio,
               cc.codcuentacredito,
               o.montooperacion, o.codtipoegresoingreso,
               o.fechahoraoperacion, o.nrocuotaplazo
        FROM foperaciones o
        JOIN dcuentacredito cc        ON cc.pkcuentacredito = o.pkcuentacredito
        JOIN dconceptooperacion co    ON co.pkconceptooperacion = o.pkconceptooperacion
        LEFT JOIN dcanaltransaccional ca ON ca.pkcanaltransaccional = o.pkcanaltransaccional
        LEFT JOIN dmediopago mp       ON mp.pkmediopago = o.pkmediopago
        WHERE cc.pkcliente = :pk
        ORDER BY o.fechahoraoperacion DESC, o.pkoperacion DESC
        LIMIT :limit
    """), {"pk": pkcliente, "limit": limit}).fetchall()


def creditos_cliente(db: Session, pkcliente: int):
    """Créditos del cliente con su saldo (para mostrar en el portal)."""
    return db.execute(text("""
        SELECT cc.codcuentacredito, f.montosaldocapital, f.diasatrasocredito,
               f.montoaprobadocredito, f.nrocuotas,
               cal.descalificacioncrediticia AS calificacion
        FROM dcuentacredito cc
        JOIN fagcuentacredito f ON f.pkcuentacredito = cc.pkcuentacredito
        LEFT JOIN dcalificacioncrediticia cal
               ON cal.pkcalificacioncrediticia = f.pkcalificacioncrediticiainterna
        WHERE cc.pkcliente = :pk AND f.periodomes = 202512
        ORDER BY cc.codcuentacredito
    """), {"pk": pkcliente}).fetchall()


def proxima_cuota(db: Session, codcuentacredito: str):
    """Primera cuota pendiente (sin pago de capital) de un crédito."""
    return db.execute(text("""
        SELECT p.pkcuentacredito, p.nrocuota, p.montocuota, p.montosaldo,
               p.fechavencimientopagocuota, p.montocapitalprogramado,
               p.pkmoneda, p.pkproducto, p.pkagencia
        FROM fplanpagomes p
        JOIN dcuentacredito cc ON cc.pkcuentacredito = p.pkcuentacredito
        WHERE cc.codcuentacredito = :cod
          AND COALESCE(p.montocapitalpagado,0) = 0
        ORDER BY p.nrocuota
        LIMIT 1
    """), {"cod": codcuentacredito}).fetchone()


def registrar_pago(db: Session, cuota, monto: float, pkcliente: int) -> dict:
    """
    Registra el pago de una cuota desde el homebanking:
    - actualiza fplanpagomes (montocapitalpagado)
    - inserta una operación en foperaciones (canal APP)
    """
    cat = db.execute(text("""
        SELECT (SELECT pkconceptooperacion FROM dconceptooperacion WHERE codconceptooperacion='PCAP') con,
               (SELECT pktipooperacion FROM dtipooperacion WHERE codtipooperacion='DEB') tipo,
               (SELECT pkmediopago FROM dmediopago WHERE codmediopago='APP') medio,
               (SELECT pkcanaltransaccional FROM dcanaltransaccional WHERE codcanaltransaccional='APP') canal,
               (SELECT pkcondicioncontable FROM dcondicioncontable WHERE codcondicioncontable='01') cond
    """)).fetchone()

    # marca la cuota como pagada (capital)
    db.execute(text("""
        UPDATE fplanpagomes
        SET montocapitalpagado = :monto, fechapagocuota = CURRENT_DATE,
            fecultactualizacion = NOW()
        WHERE pkcuentacredito = :pkcc AND nrocuota = :nro
    """), {"monto": monto, "pkcc": cuota.pkcuentacredito, "nro": cuota.nrocuota})

    # inserta el movimiento
    hoy = datetime.utcnow()
    periododia = int(hoy.strftime("%Y%m%d"))
    db.execute(text("""
        INSERT INTO foperaciones
            (codtipkar, codkardex, pkcuentacredito, nrocuotaplazo, pkconceptooperacion,
             pktipooperacion, pkmediopago, pkcanaltransaccional, pkmoneda, pkcondicioncontable,
             pkproducto, pkagenciaorigen, montooperacion, montopagoconcepto,
             codtipoegresoingreso, fechahoraoperacion, periododia, codusuope, fecultactualizacion)
        VALUES ('DB', 'PAGHB-' || :pkcc || '-' || :nro || '-' || :pd,
                :pkcc, :nro, :con, :tipo, :medio, :canal, :pkmon, :cond,
                :pkprod, :pkag, :monto, :monto, 'E', :fh, :pd, 'HBCLI', NOW())
    """), {
        "pkcc": cuota.pkcuentacredito, "nro": cuota.nrocuota,
        "con": cat.con, "tipo": cat.tipo, "medio": cat.medio, "canal": cat.canal,
        "pkmon": cuota.pkmoneda, "cond": cat.cond, "pkprod": cuota.pkproducto,
        "pkag": cuota.pkagencia, "monto": monto, "fh": hoy, "pd": periododia,
    })
    db.commit()
    return {"cuota": cuota.nrocuota, "monto_pagado": monto, "fecha": hoy.date().isoformat()}
