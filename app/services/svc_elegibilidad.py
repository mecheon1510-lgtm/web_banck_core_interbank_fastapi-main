"""
Servicio de elegibilidad del cliente — "Sujeto de Crédito".
Implementa Política de Créditos V14, numeral 2.3.A y Reglamento Art. 36.p.

Reglas duras (NO sujeto de crédito, 2.3.A.2):
  - Tiene créditos VENCIDOS o EN COBRANZA JUDICIAL en La Caja.
  - Calificación SBS Deficiente(2)/Dudoso(3)/Pérdida(4) o Castigado.
Admisión excepcional (2.3.A.3):
  - CPP(1): se puede otorgar con justificación (estado = OBSERVADO, requiere VB).
  - Def/Dud/Per: solo con opinión FAVORABLE de Gerencia de Riesgos.

Datos en BD:
  - Calificación: fagcuentacredito.pkcalificacioncrediticiainterna -> dcalificacioncrediticia
    (cod: 0 Normal, 1 CPP, 2 Deficiente, 3 Dudoso, 4 Pérdida)
  - Estado de crédito: fagcuentacredito.pkestadocredito -> destadocredito
    (02 Vencido, 03 En Cobranza Judicial, 07 Castigado)
"""
from sqlalchemy.orm import Session
from sqlalchemy import text

PERIODO_DEFECTO = 202512  # último corte disponible en la BD de ejemplo

# Resultados posibles
APTO        = "APTO"
NO_APTO     = "NO_APTO"
REQUIERE_RIESGOS = "REQUIERE_OPINION_RIESGOS"


def _peor_calificacion(db: Session, pkcliente: int, periodomes: int) -> str | None:
    """Devuelve el peor cod de calificación del cliente (0..4) o None si no tiene créditos."""
    row = db.execute(text("""
        SELECT MAX(CAST(NULLIF(TRIM(cal.codcalificacioncrediticia), '') AS INTEGER)) AS peor
        FROM fagcuentacredito f
        JOIN dcuentacredito cc ON cc.pkcuentacredito = f.pkcuentacredito
        LEFT JOIN dcalificacioncrediticia cal
               ON cal.pkcalificacioncrediticia = f.pkcalificacioncrediticiainterna
        WHERE cc.pkcliente = :pk AND f.periodomes = :per
    """), {"pk": pkcliente, "per": periodomes}).fetchone()
    if not row or row.peor is None:
        return None
    return str(row.peor)


def _tiene_vencido_o_judicial(db: Session, pkcliente: int, periodomes: int) -> bool:
    n = db.execute(text("""
        SELECT COUNT(*)
        FROM fagcuentacredito f
        JOIN dcuentacredito cc ON cc.pkcuentacredito = f.pkcuentacredito
        JOIN destadocredito e  ON e.pkestadocredito = f.pkestadocredito
        WHERE cc.pkcliente = :pk AND f.periodomes = :per
          AND e.codestadocredito IN ('02', '03', '07')
    """), {"pk": pkcliente, "per": periodomes}).scalar()
    return (n or 0) > 0


def evaluar(db: Session, pkcliente: int, periodomes: int = PERIODO_DEFECTO) -> dict:
    """
    Evalúa si el cliente es sujeto de crédito.
    Devuelve {resultado, calificacion, motivos[], requiere_opinion_riesgos}.
    """
    motivos = []
    calif = _peor_calificacion(db, pkcliente, periodomes)

    # Cliente nuevo (sin historial) -> apto, el riesgo lo cubre el scoring
    if calif is None:
        return {"resultado": APTO, "calificacion": "SIN_HISTORIAL",
                "motivos": ["Cliente sin historial crediticio en La Caja"],
                "requiere_opinion_riesgos": False}

    # Regla dura: vencidos o cobranza judicial
    if _tiene_vencido_o_judicial(db, pkcliente, periodomes):
        motivos.append("Tiene créditos vencidos o en cobranza judicial (Política 2.3.A.2.a)")
        return {"resultado": NO_APTO, "calificacion": calif,
                "motivos": motivos, "requiere_opinion_riesgos": False}

    nombres = {"0": "Normal", "1": "CPP", "2": "Deficiente", "3": "Dudoso", "4": "Pérdida"}
    desc = nombres.get(calif, calif)

    if calif == "0":
        return {"resultado": APTO, "calificacion": desc, "motivos": [],
                "requiere_opinion_riesgos": False}

    if calif == "1":  # CPP -> observado, con justificación
        motivos.append("Calificación CPP: requiere justificación y estar al día (2.3.A.3.a)")
        return {"resultado": APTO, "calificacion": desc, "motivos": motivos,
                "requiere_opinion_riesgos": False, "observado": True}

    # 2,3,4 -> Deficiente/Dudoso/Pérdida: solo con opinión favorable de Riesgos
    motivos.append(f"Calificación {desc}: solo procede con opinión favorable de "
                   f"Gerencia de Riesgos (Política 2.3.A.3.b)")
    return {"resultado": REQUIERE_RIESGOS, "calificacion": desc,
            "motivos": motivos, "requiere_opinion_riesgos": True}
