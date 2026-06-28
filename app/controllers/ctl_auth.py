from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.cfg_security import verify_password, create_access_token
from app.core.cfg_roles import rol_desde_cargo

def login(db: Session, numerodni: str, password: str):
    # DPERSONAL guarda el DNI y el nombre. El cargo real se obtiene de la tabla
    # puente dpersonalcargo -> dcargopersonal, y el asesor de la tabla puente
    # dpersonalasesor -> dasesor (dpersonal y dasesor no se cruzan naturalmente).
    sql = text("""
        SELECT p.pkpersonal, p.codpersonal, p.nombre,
               cp.codcargopersonal,
               cp.descargopersonal,
               a.pkasesor, a.codasesor
        FROM dpersonal p
        LEFT JOIN dpersonalcargo pc  ON pc.pkpersonal = p.pkpersonal
        LEFT JOIN dcargopersonal cp  ON cp.pkcargopersonal = pc.pkcargopersonal
        LEFT JOIN dpersonalasesor pa ON pa.pkpersonal = p.pkpersonal
        LEFT JOIN dasesor a          ON a.pkasesor = pa.pkasesor
        WHERE p.numerodni = :dni
        LIMIT 1
    """)
    row = db.execute(sql, {"dni": numerodni}).fetchone()
    if not row:
        return None

    # En desarrollo: password = numerodni (simplificado)
    # En producción: verify_password(password, row.password_hash)
    if password != numerodni:
        return None

    rol        = rol_desde_cargo(row.codcargopersonal)
    codagencia = "0001"  # la BD no liga persona->agencia; valor por defecto
    codasesor  = row.codasesor.strip() if row.codasesor else None

    token = create_access_token({
        "sub":         row.codpersonal,
        "pkpersonal":  row.pkpersonal,
        "pkasesor":    row.pkasesor,      # PK del asesor (None si no es asesor)
        "codasesor":   codasesor,
        "nombre":      row.nombre,
        "rol":         rol,
        "cargo":       row.descargopersonal or "Asesor de Negocios",
        "codagencia":  codagencia,
    })
    return {
        "access_token": token,
        "token_type":   "bearer",
        "codpersonal":  row.codpersonal,
        "pkasesor":     row.pkasesor,
        "codasesor":    codasesor,
        "nombre":       row.nombre,
        "rol":          rol,
        "codagencia":   codagencia,
    }