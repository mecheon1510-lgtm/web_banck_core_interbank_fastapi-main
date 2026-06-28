"""
Setup de la tabla puente persona <-> cargo (decisión §7.3 del PLAN_MPR-003-CRE).

La BD tiene el catálogo `dcargopersonal` pero ningún vínculo entre `dpersonal` y el cargo.
Este script:
  1. Crea la tabla `dpersonalcargo` (idempotente).
  2. Asigna cargos a empleados de prueba (uno por cada rol del flujo de aprobación).
  3. Asigna 'Asesor de Negocios' (E01) por defecto al resto de empleados sin cargo.

Ejecutar:  venv/Scripts/python.exe scripts/setup_dpersonalcargo.py
"""
import sys
from pathlib import Path

# permitir importar `app` cuando se ejecuta desde la raíz del proyecto
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, text  # noqa: E402
from app.core.cfg_config import settings    # noqa: E402

# DNI de prueba -> codcargopersonal (deben existir en dpersonal y dcargopersonal)
ASIGNACIONES_PRUEBA = {
    "11111111": "E01",  # Asesor de Negocios
    "11111112": "F02",  # Administrador de Agencia
    "11111113": "F01",  # Jefe de Negocios Regional
    "11111114": "F04",  # Jefe de Riesgos
    "11111115": "F05",  # Funcionario de Créditos (rol comité)
    "11111116": "E03",  # Analista de Créditos
}

DDL = """
CREATE TABLE IF NOT EXISTS dpersonalcargo (
    pkpersonalcargo   SERIAL PRIMARY KEY,
    pkpersonal        INTEGER NOT NULL REFERENCES dpersonal(pkpersonal),
    pkcargopersonal   INTEGER NOT NULL REFERENCES dcargopersonal(pkcargopersonal),
    flagactivo        CHAR(1) NOT NULL DEFAULT 'S',
    fecultactualizacion TIMESTAMP DEFAULT NOW(),
    UNIQUE (pkpersonal)
);
"""


def main():
    engine = create_engine(settings.DATABASE_URL)
    with engine.begin() as c:
        c.execute(text(DDL))
        print("[OK] tabla dpersonalcargo lista")

        # mapa codcargopersonal -> pk
        cargos = {
            r[0]: r[1]
            for r in c.execute(text(
                "SELECT codcargopersonal, pkcargopersonal FROM dcargopersonal"
            ))
        }

        # asignaciones de prueba (upsert por pkpersonal)
        for dni, codcargo in ASIGNACIONES_PRUEBA.items():
            row = c.execute(
                text("SELECT pkpersonal FROM dpersonal WHERE numerodni = :dni"),
                {"dni": dni},
            ).fetchone()
            if not row:
                print(f"[WARN] DNI {dni} no existe en dpersonal, se omite")
                continue
            pkpers = row[0]
            pkcargo = cargos.get(codcargo)
            c.execute(text("""
                INSERT INTO dpersonalcargo (pkpersonal, pkcargopersonal)
                VALUES (:p, :c)
                ON CONFLICT (pkpersonal)
                DO UPDATE SET pkcargopersonal = EXCLUDED.pkcargopersonal,
                              fecultactualizacion = NOW()
            """), {"p": pkpers, "c": pkcargo})
            print(f"[OK] DNI {dni} -> {codcargo}")

        # resto de empleados sin cargo -> Asesor de Negocios (E01)
        pk_e01 = cargos.get("E01")
        n = c.execute(text("""
            INSERT INTO dpersonalcargo (pkpersonal, pkcargopersonal)
            SELECT p.pkpersonal, :e01
            FROM dpersonal p
            WHERE NOT EXISTS (
                SELECT 1 FROM dpersonalcargo dc WHERE dc.pkpersonal = p.pkpersonal
            )
        """), {"e01": pk_e01})
        print(f"[OK] {n.rowcount} empleados restantes asignados a Asesor (E01)")

    print("\nSetup completado.")


if __name__ == "__main__":
    main()
