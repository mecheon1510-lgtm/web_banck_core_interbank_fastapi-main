"""
Puebla la dimensión de calendario dtiempo con TODOS los días 2015-2025.
Hoy solo tiene 11 filas (31/dic de cada año), lo que impide insertar operaciones
en otras fechas (foperaciones.periododia es FK a dtiempo).

Idempotente: ON CONFLICT DO NOTHING sobre periododia.
Ejecutar: venv/Scripts/python.exe scripts/seed_dtiempo.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, text   # noqa: E402
from app.core.cfg_config import settings     # noqa: E402

DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
         "Agosto", "Setiembre", "Octubre", "Noviembre", "Diciembre"]


def main():
    e = create_engine(settings.DATABASE_URL)
    # Genera fechas con SQL (generate_series) — más simple y atómico que en Python.
    with e.begin() as c:
        # 1) Primero los MESES (dtiempo.periodomes es FK a dtiempomes)
        c.execute(text("""
            INSERT INTO dtiempomes
                (periodomes, mes, anio, descripcionmes, bimestre, trimestre,
                 cuatrimestre, semestre, fecultactualizacion)
            SELECT CAST(TO_CHAR(m, 'YYYYMM') AS INTEGER),
                   EXTRACT(MONTH FROM m)::int, EXTRACT(YEAR FROM m)::int,
                   TO_CHAR(m, 'YYYY-MM'),
                   CEIL(EXTRACT(MONTH FROM m)/2.0)::int,
                   EXTRACT(QUARTER FROM m)::int,
                   CEIL(EXTRACT(MONTH FROM m)/4.0)::int,
                   CASE WHEN EXTRACT(MONTH FROM m) <= 6 THEN 1 ELSE 2 END,
                   NOW()
            FROM generate_series('2015-01-01'::date, '2027-12-01'::date, '1 month') m
            ON CONFLICT (periodomes) DO NOTHING
        """))
        mm = c.execute(text("SELECT COUNT(*) FROM dtiempomes")).scalar()
        print(f"[OK] dtiempomes total={mm}")

        antes = c.execute(text("SELECT COUNT(*) FROM dtiempo")).scalar()
        c.execute(text("""
            INSERT INTO dtiempo
                (periododia, dia, mes, anio, periodomes, descripciondia, diasemana,
                 diaanio, semanaanio, semanames, descripcionmes, feriado,
                 bimestre, trimestre, cuatrimestre, semestre, fecultactualizacion)
            SELECT
                CAST(TO_CHAR(d, 'YYYYMMDD') AS INTEGER),
                EXTRACT(DAY FROM d)::int,
                EXTRACT(MONTH FROM d)::int,
                EXTRACT(YEAR FROM d)::int,
                CAST(TO_CHAR(d, 'YYYYMM') AS INTEGER),
                TO_CHAR(d, 'DD/MM/YYYY'),
                EXTRACT(ISODOW FROM d)::int,
                EXTRACT(DOY FROM d)::int,
                EXTRACT(WEEK FROM d)::int,
                CEIL(EXTRACT(DAY FROM d) / 7.0)::int,
                TO_CHAR(d, 'YYYY-MM'),
                'N',
                CEIL(EXTRACT(MONTH FROM d) / 2.0)::int,
                EXTRACT(QUARTER FROM d)::int,
                CEIL(EXTRACT(MONTH FROM d) / 4.0)::int,
                CASE WHEN EXTRACT(MONTH FROM d) <= 6 THEN 1 ELSE 2 END,
                NOW()
            FROM generate_series('2015-01-01'::date, '2027-12-31'::date, '1 day') d
            ON CONFLICT (periododia) DO NOTHING
        """))
        despues = c.execute(text("SELECT COUNT(*) FROM dtiempo")).scalar()
        print(f"[OK] dtiempo: antes={antes} -> despues={despues} (+{despues-antes})")
    print("Listo.")


if __name__ == "__main__":
    main()
