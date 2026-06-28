"""
Realinea dnivelaprobacion a los 7 niveles del Art. 30 del Reglamento de Créditos V33.
(Corrige el desfase detectado en BRECHAS_REGLAMENTO.md §0).

Niveles (Saldo capital + monto de otorgamiento):
  N1 Asesor de Negocios          0 - 14 000   (Senior I 7k / Senior II 14k)
  N2 Administrador          14 001 - 50 000
  N3 Jefe de Negocios Reg.  50 001 - 100 000
  N4 Jefe de Producto      100 001 - 140 000
  N5 Sub Gerencia Negocios 140 001 - 170 000
  N6 Gerencia de Negocios  170 001 - 210 000
  N7 Gerencia Mancomunada  210 001 - 9 999 999 999  (hasta límite legal)

Ejecutar: venv/Scripts/python.exe scripts/realinear_nivelaprobacion.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, text
from app.core.cfg_config import settings

NIVELES = [
    ("N1", "Asesor de Negocios",          0,        14000),
    ("N2", "Administrador de Agencia",     14001,    50000),
    ("N3", "Jefe de Negocios Regional",    50001,    100000),
    ("N4", "Jefe de Producto de Créditos", 100001,   140000),
    ("N5", "Sub Gerencia de Negocios",     140001,   170000),
    ("N6", "Gerencia de Negocios",         170001,   210000),
    ("N7", "Gerencia Mancomunada",         210001,   9999999999),
]


def main():
    e = create_engine(settings.DATABASE_URL)
    with e.begin() as c:
        # ¿la columna pknivelaprobacion tiene secuencia? asumimos asignación manual
        existentes = {r[0]: r[1] for r in c.execute(text(
            "SELECT codnivelaprobacion, pknivelaprobacion FROM dnivelaprobacion"))}
        maxpk = c.execute(text("SELECT COALESCE(MAX(pknivelaprobacion),0) FROM dnivelaprobacion")).scalar()

        for i, (cod, des, mn, mx) in enumerate(NIVELES, start=1):
            if cod in existentes:
                c.execute(text("""
                    UPDATE dnivelaprobacion
                    SET desnivelaprobacion=:des, montominimo=:mn, montomaximo=:mx,
                        fecultactualizacion=NOW()
                    WHERE codnivelaprobacion=:cod
                """), {"des": des, "mn": mn, "mx": mx, "cod": cod})
                print(f"[UPD] {cod} {des} {mn}-{mx}")
            else:
                maxpk += 1
                c.execute(text("""
                    INSERT INTO dnivelaprobacion
                       (pknivelaprobacion, codnivelaprobacion, desnivelaprobacion,
                        montominimo, montomaximo, fecultactualizacion)
                    VALUES (:pk, :cod, :des, :mn, :mx, NOW())
                """), {"pk": maxpk, "cod": cod, "des": des, "mn": mn, "mx": mx})
                print(f"[INS] {cod} {des} {mn}-{mx}")

    print("\nNiveles realineados al Art. 30 V33.")


if __name__ == "__main__":
    main()
