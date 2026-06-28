from sqlalchemy.orm import Session
from app.repositories import rep_clientes, rep_creditos

# Tablas de referencia
TEA_POR_TIPO = {
    "ME": {"min": 18.50, "mid": 38.90, "max": 65.00},  # Interbank Microempresa
    "PE": {"min": 14.50, "mid": 24.90, "max": 39.00},  # Interbank Pequeña Empresa
    "CO": {"min": 29.00, "mid": 45.00, "max": 89.00},  # Interbank Consumo
    "HI": {"min":  8.50, "mid": 10.50, "max": 13.00},  # Interbank Hipotecario
    "GE": {"min": 11.00, "mid": 14.00, "max": 17.00},  # Interbank Garantizado
}

SECTORES_RIESGO = {
    # bajo riesgo
    "4711": 20, "4721": 20, "4731": 18, "5610": 18,
    "6810": 15, "8511": 15,
    # riesgo medio
    "4921": 12, "4923": 12, "0111": 10, "0112": 10,
    # riesgo alto
    "6201": 8,  "5510": 8,
}

def calcular_score(
    codcliente: str,
    montosolicitud: float,
    plazo: int,
    codtipocredito: str,
    montoingresoneto: float,
    codactividadeconomica: str,
    db: Session
) -> dict:

    observaciones = []
    detalle = {}

    # ── 1. CAPACIDAD DE PAGO (40 pts) ──────────────────────────
    tea_tipo = TEA_POR_TIPO.get(
        codtipocredito, {"min": 30.0, "mid": 40.0, "max": 55.0}
    )
    tea_ref = tea_tipo["mid"]
    tem = (1 + tea_ref / 100) ** (1 / 12) - 1
    cuota = montosolicitud * tem * (1 + tem)**plazo / ((1 + tem)**plazo - 1)
    ratio_cuota_ingreso = cuota / montoingresoneto if montoingresoneto > 0 else 1

    if ratio_cuota_ingreso <= 0.30:
        score_capacidad = 40
    elif ratio_cuota_ingreso <= 0.40:
        score_capacidad = 30
    elif ratio_cuota_ingreso <= 0.50:
        score_capacidad = 18
        observaciones.append("Cuota representa más del 40% del ingreso neto.")
    else:
        score_capacidad = 5
        observaciones.append("Cuota supera el 50% del ingreso neto — riesgo alto.")

    detalle["capacidad_pago"] = {
        "cuota_estimada": round(cuota, 2),
        "ratio_cuota_ingreso": round(ratio_cuota_ingreso * 100, 2),
        "puntaje": score_capacidad
    }

    # ── 2. HISTORIAL EN BD (30 pts) ────────────────────────────
    cliente = rep_clientes.get_by_cod(db, codcliente)
    score_historial = 0

    if not cliente:
        score_historial = 10
        observaciones.append("Cliente no registrado en la institución.")
    else:
        tiene_vencido = rep_creditos.tiene_mala_calificacion(db, cliente.pkcliente)
        if tiene_vencido:
            score_historial = 5
            observaciones.append("Cliente tiene créditos con calificación Deficiente, Dudoso o Pérdida.")
        else:
            score_historial = 30

    detalle["historial"] = {"puntaje": score_historial}

    # ── 3. SECTOR ECONÓMICO (20 pts) ───────────────────────────
    score_sector = SECTORES_RIESGO.get(codactividadeconomica, 10)
    detalle["sector_economico"] = {
        "codactividad": codactividadeconomica,
        "puntaje": score_sector
    }

    # ── 4. PLAZO (10 pts) ──────────────────────────────────────
    if plazo <= 24:
        score_plazo = 10
    elif plazo <= 48:
        score_plazo = 7
    elif plazo <= 120:
        score_plazo = 4
    else:
        score_plazo = 2
        observaciones.append("Plazo mayor a 10 años incrementa el riesgo.")

    detalle["plazo"] = {"meses": plazo, "puntaje": score_plazo}

    # ── SCORE TOTAL ─────────────────────────────────────────────
    score_total = score_capacidad + score_historial + score_sector + score_plazo
    detalle["score_total"] = score_total

    # ── DECISIÓN ────────────────────────────────────────────────
    if score_total >= 70:
        decision = "APROBADO"
        tea_sugerida = tea_tipo["min"]
    elif score_total >= 50:
        decision = "OBSERVADO"
        tea_sugerida = tea_tipo["mid"]
        observaciones.append("Requiere aprobación de jefe de agencia.")
    else:
        decision = "RECHAZADO"
        tea_sugerida = tea_tipo["max"]
        observaciones.append("Score insuficiente para aprobación automática.")

    # Recalcular cuota con TEA real sugerida
    tem_real = (1 + tea_sugerida / 100) ** (1 / 12) - 1
    cuota_final = montosolicitud * tem_real * (1+tem_real)**plazo / ((1+tem_real)**plazo - 1)

    return {
        "codcliente":      codcliente,
        "score":           round(score_total, 2),
        "decision":        decision,
        "tea_sugerida":    tea_sugerida,
        "cuota_estimada":  round(cuota_final, 2),
        "observaciones":   observaciones,
        "detalle_score":   detalle,
    }
