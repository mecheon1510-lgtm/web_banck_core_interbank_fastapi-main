"""
Recalibra fmetatipocredito + dtipocredito a los 2 productos (Empresarial=ME+PE, Consumo=CO),
para que /dashboard/evolucion-historica deje de emitir HI/MD/GE.

Reasignación: HI -> CO ; MD/GE -> PE. Los saldos/metas de los tipos eliminados se SUMAN
al tipo destino por período (consolidación, sin duplicar filas).

Respaldo previo: backups/backup_metas_YYYYMMDD.sql
Ejecutar: venv/Scripts/python.exe scripts/recalibrar_metas.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, text
from app.core.cfg_config import settings

# tipo origen -> tipo destino (por codtipocredito)
REASIGNAR = {"HI": "CO", "MD": "PE", "GE": "PE"}

# columnas numéricas de fmetatipocredito a consolidar (sumar)
COLS = ["saldocolocaciones_meta", "saldocolocaciones_real",
        "ratiomora_meta", "ratiomora_real"]


def main():
    e = create_engine(settings.DATABASE_URL, isolation_level="AUTOCOMMIT")
    with e.connect() as c:
        # mapa cod -> pk
        pk = {r[0].strip(): r[1] for r in c.execute(text(
            "SELECT codtipocredito, pktipocredito FROM dtipocredito"))}

        # columnas reales presentes en la tabla (por si difieren)
        cols_tabla = {r[0] for r in c.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_name='fmetatipocredito'"))}
        sum_cols = [col for col in COLS if col in cols_tabla]

        movidos = 0
        for cod_ori, cod_des in REASIGNAR.items():
            if cod_ori not in pk or cod_des not in pk:
                continue
            pk_ori, pk_des = pk[cod_ori], pk[cod_des]

            # por cada periodo del origen: si existe destino -> sumar; si no -> reasignar pk
            periodos = [r[0] for r in c.execute(text(
                "SELECT periodomes FROM fmetatipocredito WHERE pktipocredito=:o"), {"o": pk_ori})]
            for per in periodos:
                existe_des = c.execute(text(
                    "SELECT 1 FROM fmetatipocredito WHERE pktipocredito=:d AND periodomes=:p"),
                    {"d": pk_des, "p": per}).fetchone()
                if existe_des:
                    set_sql = ", ".join(
                        f"{col} = COALESCE(d.{col},0) + COALESCE(o.{col},0)" for col in sum_cols)
                    c.execute(text(f"""
                        UPDATE fmetatipocredito d
                        SET {set_sql}, fecultactualizacion = NOW()
                        FROM fmetatipocredito o
                        WHERE d.pktipocredito=:d AND d.periodomes=:p
                          AND o.pktipocredito=:o AND o.periodomes=:p
                    """), {"d": pk_des, "o": pk_ori, "p": per})
                    c.execute(text(
                        "DELETE FROM fmetatipocredito WHERE pktipocredito=:o AND periodomes=:p"),
                        {"o": pk_ori, "p": per})
                else:
                    c.execute(text(
                        "UPDATE fmetatipocredito SET pktipocredito=:d WHERE pktipocredito=:o AND periodomes=:p"),
                        {"d": pk_des, "o": pk_ori, "p": per})
                movidos += 1
            print(f"[OK] {cod_ori} -> {cod_des}: {len(periodos)} periodos")

        # eliminar tipos fuera de alcance del catálogo (si ya no se referencian)
        for cod in REASIGNAR:
            try:
                c.execute(text("DELETE FROM dtipocredito WHERE codtipocredito=:c"), {"c": cod})
                print(f"[OK] dtipocredito eliminado: {cod}")
            except Exception as ex:
                print(f"[WARN] no se pudo eliminar {cod}: {str(ex)[:80]}")

        print("--- tipos restantes en fmetatipocredito ---")
        for r in c.execute(text("""SELECT t.codtipocredito, COUNT(*) n
            FROM fmetatipocredito m JOIN dtipocredito t ON t.pktipocredito=m.pktipocredito
            GROUP BY 1 ORDER BY 1""")):
            print(f"   tipo={r[0].strip()} n={r[1]}")
    print("Recalibración de metas completada.")


if __name__ == "__main__":
    main()
