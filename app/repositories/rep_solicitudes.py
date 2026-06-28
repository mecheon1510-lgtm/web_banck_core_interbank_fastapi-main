"""
Repositorio de solicitudes de crédito (tabla dsolicitud) — MPR-003-CRE.

Notas del esquema real:
- dsolicitud.pksolicitud usa la secuencia dsolicitud_pksolicitud_seq (DEFAULT nextval).
  Se obtiene el pk de la secuencia y el codsolicitud se deriva de él ('SOL'+7 díg.),
  todo en un único INSERT atómico (evita colisiones y condiciones de carrera).
- Solo pksolicitud y codsolicitud son NOT NULL; el resto es opcional.
"""
from datetime import datetime, date
from sqlalchemy.orm import Session
from sqlalchemy import text

# Estados (dsolicitudestado)
ESTADO_EN_EVALUACION = 1
ESTADO_APROBADO      = 2
ESTADO_RECHAZADO     = 3
ESTADO_DESEMBOLSADO  = 4
ESTADO_ANULADO       = 5
ESTADO_EN_COMITE     = 6


def _pkmoneda_soles(db: Session) -> int:
    """Resuelve la PK de la moneda Soles; fallback a 1."""
    row = db.execute(text(
        "SELECT pkmoneda FROM dmoneda "
        "WHERE UPPER(codmoneda) IN ('PEN','S','S/','SOL','SO') "
        "   OR UPPER(desmoneda) LIKE '%SOL%' "
        "ORDER BY pkmoneda LIMIT 1"
    )).scalar()
    return int(row) if row else 1


def _pkproducto_por_tipo(db: Session, codtipocredito: str) -> int:
    """Primer producto del tipo de crédito dado; fallback al primero existente."""
    row = db.execute(text(
        "SELECT pkproducto FROM dproducto WHERE codtipocredito = :t "
        "ORDER BY pkproducto LIMIT 1"
    ), {"t": codtipocredito}).scalar()
    if row:
        return int(row)
    return int(db.execute(text("SELECT MIN(pkproducto) FROM dproducto")).scalar() or 1)


def _pkagencia_default(db: Session) -> int:
    return int(db.execute(text("SELECT MIN(pkagencia) FROM dagencia")).scalar() or 1)


def _pkasesor_default(db: Session) -> int:
    return int(db.execute(text("SELECT MIN(pkasesor) FROM dasesor")).scalar() or 1)


def nivel_por_monto(db: Session, monto: float):
    """Devuelve la fila de dnivelaprobacion cuyo rango contiene el monto."""
    return db.execute(text("""
        SELECT pknivelaprobacion, codnivelaprobacion, desnivelaprobacion,
               montominimo, montomaximo
        FROM dnivelaprobacion
        WHERE :monto >= montominimo AND :monto <= montomaximo
        ORDER BY montominimo
        LIMIT 1
    """), {"monto": monto}).fetchone()


def crear(db: Session, *, pkcliente: int, pkasesor: int | None,
          monto: float, plazo: int, nrocuotas: int,
          codtipocredito: str, pknivelaprobacion: int | None,
          estado: int = ESTADO_EN_EVALUACION,
          motivo: str = "Nueva solicitud") -> dict:
    """
    Inserta una solicitud usando la secuencia de BD para pksolicitud (atómico).
    El codsolicitud se deriva del pk recién asignado: 'SOL' + pk a 7 dígitos.
    """
    ahora = datetime.utcnow()
    row = db.execute(text("""
        INSERT INTO dsolicitud (
            pksolicitud, codsolicitud, pkcliente, pkasesor, pkagencia, pkproducto,
            pksolicitudestado, pksolicitudsituacion, pkmoneda, pknivelaprobacion,
            montosolicitudcredito, plazosolicitudcredito, nrocuotasolicitud,
            nrodiasgracia, nrodiasgraciaaprobado, flaglibreamortizacioncredito,
            codtiposolicitud, destiposolicitud, desmotivosolicitud,
            fechasolicitudcredito, fechahoracreacion, fechahoraultmodificacion,
            fecultactualizacion
        ) VALUES (
            nextval('dsolicitud_pksolicitud_seq'),
            'SOL' || LPAD(currval('dsolicitud_pksolicitud_seq')::text, 7, '0'),
            :pkcliente, :pkasesor, :pkagencia, :pkproducto,
            :estado, 1, :pkmoneda, :pknivel,
            :monto, :plazo, :ncuotas,
            0, 0, 'N',
            '01', 'Nueva Solicitud', :motivo,
            :hoy, :ahora, :ahora,
            :ahora
        )
        RETURNING pksolicitud, codsolicitud
    """), {
        "pkcliente": pkcliente,
        "pkasesor": pkasesor or _pkasesor_default(db),
        "pkagencia": _pkagencia_default(db),
        "pkproducto": _pkproducto_por_tipo(db, codtipocredito),
        "estado": estado, "pkmoneda": _pkmoneda_soles(db),
        "pknivel": pknivelaprobacion,
        "monto": monto, "plazo": plazo, "ncuotas": nrocuotas,
        "motivo": (motivo or "")[:80],  # desmotivosolicitud es varchar(80)
        "hoy": date.today(), "ahora": ahora,
    }).fetchone()
    db.commit()
    return {"pksolicitud": row.pksolicitud, "codsolicitud": row.codsolicitud}


def obtener(db: Session, codsolicitud: str):
    return db.execute(text("""
        SELECT s.pksolicitud, s.codsolicitud, s.pkcliente, cl.codcliente, cl.nomcliente,
               s.montosolicitudcredito, s.plazosolicitudcredito, s.nrocuotasolicitud,
               s.codtiposolicitud, s.pksolicitudestado, e.dessolicitudestado,
               s.pknivelaprobacion, na.desnivelaprobacion,
               s.montoaprobadocredito, s.fechaaprobacioncredito,
               s.desmotivosolicitud, s.fechasolicitudcredito
        FROM dsolicitud s
        LEFT JOIN dcliente cl          ON cl.pkcliente = s.pkcliente
        LEFT JOIN dsolicitudestado e   ON e.pksolicitudestado = s.pksolicitudestado
        LEFT JOIN dnivelaprobacion na  ON na.pknivelaprobacion = s.pknivelaprobacion
        WHERE s.codsolicitud = :cod
        LIMIT 1
    """), {"cod": codsolicitud}).fetchone()


def listar(db: Session, *, estado: int | None = None, search: str | None = None,
           fec_ini: str | None = None, fec_fin: str | None = None,
           limit: int = 50, offset: int = 0):
    """Listado de solicitudes para la bandeja (filtros opcionales: estado, búsqueda, rango de fechas)."""
    where, params = [], {"limit": limit, "offset": offset}
    if estado is not None:
        where.append("s.pksolicitudestado = :estado")
        params["estado"] = estado
    if search:
        where.append("(s.codsolicitud ILIKE :q OR cl.nomcliente ILIKE :q)")
        params["q"] = f"%{search}%"
    if fec_ini:
        where.append("s.fechasolicitudcredito >= :fec_ini")
        params["fec_ini"] = fec_ini
    if fec_fin:
        where.append("s.fechasolicitudcredito <= :fec_fin")
        params["fec_fin"] = fec_fin
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    return db.execute(text(f"""
        SELECT s.pksolicitud, s.codsolicitud, s.pkcliente, cl.codcliente, cl.nomcliente,
               s.montosolicitudcredito, s.plazosolicitudcredito,
               s.codtiposolicitud, s.pksolicitudestado, e.dessolicitudestado,
               s.pknivelaprobacion, na.desnivelaprobacion,
               s.montoaprobadocredito, s.fechaaprobacioncredito,
               s.desmotivosolicitud, s.fechasolicitudcredito
        FROM dsolicitud s
        LEFT JOIN dcliente cl          ON cl.pkcliente = s.pkcliente
        LEFT JOIN dsolicitudestado e   ON e.pksolicitudestado = s.pksolicitudestado
        LEFT JOIN dnivelaprobacion na  ON na.pknivelaprobacion = s.pknivelaprobacion
        {where_sql}
        ORDER BY s.pksolicitud DESC
        LIMIT :limit OFFSET :offset
    """), params).fetchall()


def resumen(db: Session):
    """Conteo de solicitudes por estado (para KPIs de la bandeja)."""
    return db.execute(text("""
        SELECT s.pksolicitudestado, e.dessolicitudestado, COUNT(*) AS n
        FROM dsolicitud s
        LEFT JOIN dsolicitudestado e ON e.pksolicitudestado = s.pksolicitudestado
        GROUP BY s.pksolicitudestado, e.dessolicitudestado
        ORDER BY s.pksolicitudestado
    """)).fetchall()


def cambiar_estado(db: Session, codsolicitud: str, nuevo_estado: int,
                   *, motivo: str | None = None,
                   monto_aprobado: float | None = None,
                   pkcomite: int | None = None) -> bool:
    sets = ["pksolicitudestado = :estado", "fechahoraultmodificacion = :ahora",
            "fecultactualizacion = :ahora"]
    params = {"estado": nuevo_estado, "ahora": datetime.utcnow(), "cod": codsolicitud}
    if motivo is not None:
        sets.append("desmotivosolicitud = :motivo")
        params["motivo"] = motivo
    if pkcomite is not None:
        sets.append("pkcomite = :pkcomite")
        params["pkcomite"] = pkcomite
    if nuevo_estado == ESTADO_APROBADO:
        sets.append("montoaprobadocredito = :maprob")
        sets.append("fechaaprobacioncredito = :faprob")
        params["maprob"] = monto_aprobado
        params["faprob"] = date.today()
    res = db.execute(text(
        "UPDATE dsolicitud SET " + ", ".join(sets) + " WHERE codsolicitud = :cod"
    ), params)
    db.commit()
    return res.rowcount > 0
