"""
R2 — Crea la infraestructura de Gestión de Cobranza (Recuperaciones).

Tablas nuevas:
  - dtipogestioncobranza: catálogo de acciones (SMS, LLAMADA, VISITA, CARTA, COMPROMISO).
  - fgestioncobranza: registro de cada gestión sobre un crédito moroso.

Idempotente (CREATE TABLE IF NOT EXISTS / ON CONFLICT).
Ejecutar: venv/Scripts/python.exe scripts/setup_recuperaciones.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, text
from app.core.cfg_config import settings

DDL_TIPO = """
CREATE TABLE IF NOT EXISTS dtipogestioncobranza (
    pktipogestion   SERIAL PRIMARY KEY,
    codtipogestion  VARCHAR(10) UNIQUE NOT NULL,
    destipogestion  VARCHAR(60) NOT NULL,
    fecultactualizacion TIMESTAMP DEFAULT NOW()
);
"""

DDL_GESTION = """
CREATE TABLE IF NOT EXISTS fgestioncobranza (
    pkgestion        BIGSERIAL PRIMARY KEY,
    pkcuentacredito  INTEGER NOT NULL REFERENCES dcuentacredito(pkcuentacredito),
    pktipogestion    INTEGER NOT NULL REFERENCES dtipogestioncobranza(pktipogestion),
    fechagestion     DATE NOT NULL DEFAULT CURRENT_DATE,
    diasatrasoalmomento INTEGER,
    banda            VARCHAR(20),         -- PREVENTIVA|TEMPRANA|TARDIA|JUDICIAL|CASTIGO
    gestor           VARCHAR(20),         -- codpersonal del gestor
    resultado        VARCHAR(120),
    compromisopago   DATE,                -- fecha comprometida de pago (si aplica)
    montocomprometido NUMERIC(14,2),
    fecultactualizacion TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_fgestion_credito ON fgestioncobranza(pkcuentacredito);
"""

TIPOS = [
    ("SMS", "Envío de SMS"),
    ("LLAM", "Llamada telefónica"),
    ("VISI", "Visita domiciliaria"),
    ("CART", "Carta / notificación"),
    ("COMP", "Compromiso de pago"),
    ("JUDI", "Derivación judicial"),
]


def main():
    e = create_engine(settings.DATABASE_URL, isolation_level="AUTOCOMMIT")
    with e.connect() as c:
        c.execute(text(DDL_TIPO))
        c.execute(text(DDL_GESTION))
        print("[OK] tablas dtipogestioncobranza / fgestioncobranza listas")
        for cod, des in TIPOS:
            c.execute(text("""
                INSERT INTO dtipogestioncobranza (codtipogestion, destipogestion, fecultactualizacion)
                VALUES (:c, :d, NOW()) ON CONFLICT (codtipogestion) DO NOTHING
            """), {"c": cod, "d": des})
        n = c.execute(text("SELECT COUNT(*) FROM dtipogestioncobranza")).scalar()
        print(f"[OK] catálogo tipos de gestión: {n} filas")
    print("Setup recuperaciones completado.")


if __name__ == "__main__":
    main()
