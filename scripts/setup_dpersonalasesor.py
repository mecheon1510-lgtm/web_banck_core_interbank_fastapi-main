"""
Setup de la tabla puente persona <-> asesor (dpersonalasesor).

Motivo: dpersonal (personal/usuarios) y dasesor (asesores del datamart) son
catálogos sin relación natural (0 coinciden por código). Para que el token del
login lleve el pkasesor del usuario, se crea esta tabla puente.

Estrategia (decisión del usuario): a los empleados de PRUEBA se les asigna un
pkasesor que SÍ tiene cartera en 202512, para que "Mi cartera" muestre datos.
El resto de empleados con rol asesor (E01) se asignan a los asesores restantes.

Ejecutar: venv/Scripts/python.exe scripts/setup_dpersonalasesor.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, text  # noqa: E402
from app.core.cfg_config import settings    # noqa: E402

# DNI de prueba -> pkasesor con cartera real (de la inspección: 31,36,12,18,40,78)
ASIGNACIONES_PRUEBA = {
    "11111111": 31,  # asesor con 22 créditos -> Mi cartera con datos
    "11111112": 36,
    "11111113": 12,
    "11111114": 18,
    "11111115": 40,
    "11111116": 78,
}

DDL = """
CREATE TABLE IF NOT EXISTS dpersonalasesor (
    pkpersonalasesor   SERIAL PRIMARY KEY,
    pkpersonal         INTEGER NOT NULL REFERENCES dpersonal(pkpersonal),
    pkasesor           INTEGER NOT NULL REFERENCES dasesor(pkasesor),
    flagactivo         CHAR(1) NOT NULL DEFAULT 'S',
    fecultactualizacion TIMESTAMP DEFAULT NOW(),
    UNIQUE (pkpersonal)
);
"""


def main():
    engine = create_engine(settings.DATABASE_URL)
    with engine.begin() as c:
        c.execute(text(DDL))
        print("[OK] tabla dpersonalasesor lista")

        # asignaciones de prueba (upsert por pkpersonal)
        for dni, pkasesor in ASIGNACIONES_PRUEBA.items():
            pkpers = c.execute(text(
                "SELECT pkpersonal FROM dpersonal WHERE numerodni = :dni"),
                {"dni": dni}).scalar()
            if not pkpers:
                print(f"[WARN] DNI {dni} no existe, se omite")
                continue
            c.execute(text("""
                INSERT INTO dpersonalasesor (pkpersonal, pkasesor)
                VALUES (:p, :a)
                ON CONFLICT (pkpersonal)
                DO UPDATE SET pkasesor = EXCLUDED.pkasesor, fecultactualizacion = NOW()
            """), {"p": pkpers, "a": pkasesor})
            print(f"[OK] DNI {dni} -> pkasesor {pkasesor}")

        # resto de empleados con rol asesor (E01) sin asignación -> repartir entre
        # los pkasesor existentes de forma determinística (módulo sobre total asesores)
        total_asesores = c.execute(text("SELECT COUNT(*) FROM dasesor")).scalar()
        pendientes = c.execute(text("""
            SELECT p.pkpersonal
            FROM dpersonal p
            JOIN dpersonalcargo pc ON pc.pkpersonal = p.pkpersonal
            JOIN dcargopersonal cp ON cp.pkcargopersonal = pc.pkcargopersonal
            WHERE cp.codcargopersonal = 'E01'
              AND NOT EXISTS (SELECT 1 FROM dpersonalasesor da WHERE da.pkpersonal = p.pkpersonal)
            ORDER BY p.pkpersonal
        """)).fetchall()
        # pkasesor válidos ordenados
        asesores = [r[0] for r in c.execute(text("SELECT pkasesor FROM dasesor ORDER BY pkasesor"))]
        asignados = 0
        for i, (pkpers,) in enumerate(pendientes):
            pka = asesores[i % len(asesores)]
            c.execute(text("""
                INSERT INTO dpersonalasesor (pkpersonal, pkasesor)
                VALUES (:p, :a) ON CONFLICT (pkpersonal) DO NOTHING
            """), {"p": pkpers, "a": pka})
            asignados += 1
        print(f"[OK] {asignados} empleados asesores restantes asignados (round-robin)")

    print("\nSetup completado.")


if __name__ == "__main__":
    main()
