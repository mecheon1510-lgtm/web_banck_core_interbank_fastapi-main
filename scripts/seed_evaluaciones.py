"""
FASE 2 — Generador de evaluaciones crediticias (alcance: Microempresa y Consumo).

Para cada solicitud cuyo producto es ME (01) o CO (03), genera de forma coherente:
  1. fclientefuenteingreso  — fuente de ingreso del cliente (negocio si ME, planilla si CO).
  2. devaluacion            — cabecera de la evaluación, ligada a codsolicitud.
  3. fevalconsumo (CO)      — ingresos vs gastos familiares.
     fevalmicroactivo (ME)  — activos del negocio (disponible/inventario/fijo).

Coherencia:
  - El ingreso del cliente (dcliente.montoingresoneto) es la base.
  - Gastos familiares ~ 35-45% del ingreso.
  - ME: activos del negocio proporcionales al monto solicitado.
  - CO: monto evaluado = ingreso neto del cliente.

Idempotente: no duplica devaluacion por codsolicitud.
Ejecutar: venv/Scripts/python.exe scripts/seed_evaluaciones.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, text   # noqa: E402
from app.core.cfg_config import settings     # noqa: E402

PERIODO = 202512  # periodo de referencia (existe en dtiempomes)


def solicitudes_en_alcance(c):
    """Solicitudes ME(01) / CO(03) que aún no tienen evaluación."""
    return c.execute(text("""
        SELECT s.codsolicitud, s.pkcliente, s.montosolicitudcredito,
               p.codtipocredito, cl.montoingresoneto, cl.pkactividadeconomica
        FROM dsolicitud s
        JOIN dproducto p ON p.pkproducto = s.pkproducto
        JOIN dcliente cl ON cl.pkcliente = s.pkcliente
        WHERE p.codtipocredito IN ('01', '03')
          AND NOT EXISTS (SELECT 1 FROM devaluacion d WHERE d.codsolicitud = s.codsolicitud)
        ORDER BY s.pksolicitud
    """)).fetchall()


def main():
    e = create_engine(settings.DATABASE_URL)
    n_ing = n_eval = n_co = n_me = 0
    with e.begin() as c:
        sols = solicitudes_en_alcance(c)
        print(f"[INFO] solicitudes ME/CO sin evaluación: {len(sols)}")

        for s in sols:
            cod = s.codsolicitud
            es_me = s.codtipocredito == "01"
            ingreso = float(s.montoingresoneto or 1500)
            monto = float(s.montosolicitudcredito or 0)
            gasto_fam = round(ingreso * 0.40, 2)  # 40% del ingreso

            # 1) Fuente de ingreso (idempotente por cliente+periodo+tipo)
            r = c.execute(text("""
                INSERT INTO fclientefuenteingreso
                    (pkcliente, periodomes, tipofuenteingreso, montofuenteingreso,
                     codrelacion, pkactividadeconomicacliente, nombreempresa, fecultactualizacion)
                SELECT :pk, :per, :tipo, :monto, 'T', :pkact, :emp, NOW()
                WHERE NOT EXISTS (
                    SELECT 1 FROM fclientefuenteingreso f
                    WHERE f.pkcliente=:pk AND f.periodomes=:per AND f.tipofuenteingreso=:tipo)
            """), {
                "pk": s.pkcliente, "per": PERIODO,
                "tipo": "NE" if es_me else "DE",   # NE=negocio, DE=dependiente
                "monto": ingreso, "pkact": s.pkactividadeconomica,
                "emp": "Negocio propio" if es_me else "Empleador",
            })
            n_ing += r.rowcount

            # 2) Cabecera de evaluación (devaluacion) — pk por secuencia
            row = c.execute(text("""
                INSERT INTO devaluacion
                    (nroevaluacion, valorexcedentecredito, tipoevaluacion, codsolicitud, fecultactualizacion)
                VALUES ('EV-' || :cod, :exc, :tipo, :cod, NOW())
                RETURNING pkevaluacion
            """), {
                "cod": cod,
                "exc": round(ingreso - gasto_fam, 2),  # excedente = ingreso - gastos
                "tipo": "ME" if es_me else "CO",
            }).fetchone()
            pkeval = row.pkevaluacion
            n_eval += 1

            # 3) Detalle según tipo
            if es_me:
                # Activos del negocio proporcionales al monto solicitado
                c.execute(text("""
                    INSERT INTO fevalmicroactivo
                        (pkevaluacion, nroreg, montoactivodisponible, montoactivoinventario,
                         montoactivofijo, montogastofamiliar, fecultactualizacion)
                    VALUES (:pk, 1, :disp, :inv, :fijo, :gf, NOW())
                """), {
                    "pk": pkeval,
                    "disp": round(monto * 0.20, 2),   # caja/bancos
                    "inv": round(monto * 0.50, 2),    # mercadería
                    "fijo": round(monto * 0.80, 2),   # maquinaria/local
                    "gf": gasto_fam,
                })
                n_me += 1
            else:
                # Consumo: ingreso vs gasto familiar
                c.execute(text("""
                    INSERT INTO fevalconsumo
                        (pkevaluacion, monto, montogastofamiliar, codtipoingreso,
                         fortalezaevaluacion, debilidadevaluacion, fecultactualizacion)
                    VALUES (:pk, :monto, :gf, 'D',
                            'Ingreso dependiente estable', 'Sin garantía real', NOW())
                """), {"pk": pkeval, "monto": ingreso, "gf": gasto_fam})
                n_co += 1

        print(f"[OK] fuentes de ingreso nuevas: {n_ing}")
        print(f"[OK] evaluaciones (devaluacion): {n_eval}  (ME={n_me}, CO={n_co})")
        tot = c.execute(text("SELECT COUNT(*) FROM devaluacion")).scalar()
        print(f"[TOTAL] devaluacion={tot}")
    print("Fase 2 completada.")


if __name__ == "__main__":
    main()
