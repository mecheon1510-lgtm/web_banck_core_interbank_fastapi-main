"""
Recalibración de la cartera de crédito a 2 productos (Empresarial / Consumo) y a las
proporciones REALES de Caja Huancayo (datos SGN, ver cfg_calibracion).

Enfoque QUIRÚRGICO (no borra clientes/ahorros/homebanking; respeta FKs):
  1. Reasigna los créditos de productos fuera de alcance (Hipotecario/Mediana/Gran empresa)
     a productos en alcance: empresariales grandes -> Pequeña Empresa (PE), resto -> Consumo (CO).
  2. Recalibra la CALIFICACIÓN crediticia de toda la cartera a la distribución real
     (Normal 82.6% / CPP 3.2% / Deficiente 1.5% / Dudoso 1.7% / Pérdida 11%) y ajusta los
     días de mora coherentes con cada banda (MORA_POR_CALIFICACION).
  3. Marca RDS ~3.7% y recalcula montosaldovencido/normal según calificación.
  4. Elimina del catálogo dproducto los productos fuera de alcance (HI/MD/GE).

Respaldo previo: backups/backup_cartera_YYYYMMDD.sql (pg_dump --data-only).
Ejecutar: venv/Scripts/python.exe scripts/recalibrar_cartera.py
"""
import sys, random
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, text
from app.core.cfg_config import settings
from app.core.cfg_calibracion import CALIFICACION_RCC, MORA_POR_CALIFICACION, RDS_EXPUESTO

# Determinístico (sin random global del que advierte el entorno): semilla fija local
rng = random.Random(20260602)

# pkcalificacioncrediticia por código (de la BD): 0->1,1->2,2->3,3->4,4->5
CALIF_PK = {"0": 1, "1": 2, "2": 3, "3": 4, "4": 5}


def calificacion_aleatoria() -> str:
    """Devuelve un cod de calificación según las probabilidades reales."""
    r = rng.random()
    acc = 0.0
    for cod, p in CALIFICACION_RCC.items():
        acc += p
        if r <= acc:
            return cod
    return "0"


def mora_para(cod: str) -> int:
    lo, hi = MORA_POR_CALIFICACION[cod]
    return rng.randint(lo, hi)


def main():
    e = create_engine(settings.DATABASE_URL, isolation_level="AUTOCOMMIT")
    with e.connect() as c:
        # --- 1. Reasignar créditos de productos fuera de alcance ---
        # PE destino (pequeña empresa) y CO destino (consumo), tomamos el primer pkproducto de cada uno
        pk_pe = c.execute(text("SELECT MIN(pkproducto) FROM dproducto WHERE codtipocredito='02'")).scalar()
        pk_co = c.execute(text("SELECT MIN(pkproducto) FROM dproducto WHERE codtipocredito='03'")).scalar()

        # Hipotecario(04) y Mediana(05)/Gran(06) empresa -> los empresariales a PE, hipotecario a CO
        mov_emp = c.execute(text("""
            UPDATE fagcuentacredito SET pkproducto=:pe
            WHERE pkproducto IN (SELECT pkproducto FROM dproducto WHERE codtipocredito IN ('05','06'))
        """), {"pe": pk_pe}).rowcount
        mov_hip = c.execute(text("""
            UPDATE fagcuentacredito SET pkproducto=:co
            WHERE pkproducto IN (SELECT pkproducto FROM dproducto WHERE codtipocredito IN ('04'))
        """), {"co": pk_co}).rowcount
        # lo mismo en fplanpagomes y dsolicitud por consistencia
        for tabla in ("fplanpagomes", "dsolicitud"):
            c.execute(text(f"""
                UPDATE {tabla} SET pkproducto=:pe
                WHERE pkproducto IN (SELECT pkproducto FROM dproducto WHERE codtipocredito IN ('05','06'))
            """), {"pe": pk_pe})
            c.execute(text(f"""
                UPDATE {tabla} SET pkproducto=:co
                WHERE pkproducto IN (SELECT pkproducto FROM dproducto WHERE codtipocredito IN ('04'))
            """), {"co": pk_co})
        print(f"[OK] reasignados: {mov_emp} (Mediana/Gran->PE), {mov_hip} (Hipotecario->CO)")

        # --- 2. Recalibrar calificación + mora de toda la cartera ---
        creditos = [r[0] for r in c.execute(text(
            "SELECT pkcuentacredito FROM fagcuentacredito WHERE periodomes=202512"))]
        actualizados = 0
        for pkcc in creditos:
            cod = calificacion_aleatoria()
            mora = mora_para(cod)
            rds = "S" if rng.random() < RDS_EXPUESTO else "N"
            c.execute(text("""
                UPDATE fagcuentacredito
                SET pkcalificacioncrediticiainterna=:pkcal,
                    diasatrasocredito=:mora,
                    car_ven_capital = CASE WHEN :cod='0' THEN 0 ELSE COALESCE(montosaldocapital,0) END,
                    car_vig_capital = CASE WHEN :cod='0' THEN COALESCE(montosaldocapital,0) ELSE 0 END,
                    montosaldovencido = CASE WHEN :cod='0' THEN 0 ELSE COALESCE(montosaldocapital,0) END,
                    montosaldonormal  = CASE WHEN :cod='0' THEN COALESCE(montosaldocapital,0) ELSE 0 END,
                    fecultactualizacion=NOW()
                WHERE pkcuentacredito=:pkcc AND periodomes=202512
            """), {"pkcal": CALIF_PK[cod], "mora": mora, "cod": cod, "pkcc": pkcc})
            actualizados += 1
        print(f"[OK] cartera recalibrada: {actualizados} créditos (calificación+mora+RDS)")

        # --- 3. Eliminar del catálogo los productos fuera de alcance ---
        # (ya no quedan créditos apuntando a ellos)
        elim = c.execute(text("""
            DELETE FROM dproducto WHERE codtipocredito IN ('04','05','06')
              AND pkproducto NOT IN (SELECT DISTINCT pkproducto FROM fagcuentacredito WHERE pkproducto IS NOT NULL)
              AND pkproducto NOT IN (SELECT DISTINCT pkproducto FROM fplanpagomes WHERE pkproducto IS NOT NULL)
              AND pkproducto NOT IN (SELECT DISTINCT pkproducto FROM dsolicitud WHERE pkproducto IS NOT NULL)
        """)).rowcount
        print(f"[OK] productos eliminados del catálogo: {elim}")

    print("Recalibración completada.")


if __name__ == "__main__":
    main()
