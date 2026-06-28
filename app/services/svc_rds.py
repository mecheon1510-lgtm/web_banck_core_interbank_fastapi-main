"""
Servicio de Riesgo de Sobreendeudamiento (RDS).
Implementa los ratios y límites de apetito/tolerancia del Reglamento de Créditos V33, Art. 13.

Ratios (para créditos minoristas y consumo):
  1) Cuota / Ingreso o Ventas
  2) Deuda Total / Excedente
  3) Cuota / Excedente
  4) N.º de entidades en el sistema financiero (incluida La Caja)

Límites (Art. 13 - Cuadro de Apetito y Tolerancia):
  MICROEMPRESA / PEQUEÑA:
    cuota/ingreso  apetito <=90%  tolerancia <=200%
    deuda/excedente apetito <=75v  tolerancia <=200v
    cuota/excedente apetito <=85%(nuevo)/90%(recurrente) tol <=95%/100%
  CONSUMO:
    cuota/ingreso  apetito <=70%  tolerancia <=100%
    cuota/excedente apetito <=35-40% (por convenio <=50%) tol <=80%
  N.º entidades: apetito 4, tolerancia 6.

Datos:
  - ingreso neto: dcliente.montoingresoneto
  - deuda/cuotas externas y n.º de entidades: NO están en la BD -> entran como parámetros
    opcionales desde la solicitud (endeudamiento_global, n_entidades, cuotas_sf).
"""

# Semáforo de resultado por ratio
VERDE     = "VERDE"      # dentro de apetito
AMARILLO  = "AMARILLO"   # entre apetito y tolerancia
ROJO      = "ROJO"       # supera tolerancia

# Límites por tipo de crédito (apetito, tolerancia)
LIMITES = {
    "ME": {"cuota_ingreso": (90, 200), "deuda_excedente": (75, 200), "cuota_excedente": (85, 95)},
    "PE": {"cuota_ingreso": (90, 200), "deuda_excedente": (75, 200), "cuota_excedente": (85, 95)},
    "CO": {"cuota_ingreso": (70, 100), "deuda_excedente": (75, 200), "cuota_excedente": (40, 80)},
    "HI": {"cuota_ingreso": (70, 100), "deuda_excedente": (75, 200), "cuota_excedente": (40, 80)},
}
LIMITE_ENTIDADES = (4, 6)  # apetito, tolerancia


def _semaforo(valor: float, apetito: float, tolerancia: float) -> str:
    if valor <= apetito:
        return VERDE
    if valor <= tolerancia:
        return AMARILLO
    return ROJO


def evaluar(*, codtipocredito: str, cuota_propuesta: float, ingreso_neto: float,
            cuotas_sistema_financiero: float = 0.0,
            deuda_externa_total: float = 0.0,
            gastos_familiares: float = 0.0,
            n_entidades: int | None = None,
            es_recurrente: bool = False) -> dict:
    """
    Calcula los ratios RDS y su semáforo.
    - cuota_propuesta: cuota mensual del crédito solicitado.
    - ingreso_neto: ingreso/ventas neto mensual del cliente.
    - cuotas_sistema_financiero: suma de cuotas mensuales en otras entidades.
    - deuda_externa_total: saldo de deuda en el sistema financiero (centrales).
    - gastos_familiares: egresos familiares mensuales (para excedente).
    - n_entidades: n.º de entidades incl. La Caja (None si se desconoce).
    """
    tipo = codtipocredito if codtipocredito in LIMITES else "CO"
    lim = LIMITES[tipo]
    idx_excedente = 1 if es_recurrente else 0  # apetito recurrente más laxo en cuota/excedente

    cuota_total = cuota_propuesta + cuotas_sistema_financiero
    excedente = max(ingreso_neto - cuotas_sistema_financiero - gastos_familiares, 0.0)

    ratios = {}

    # 1) Cuota / Ingreso
    if ingreso_neto > 0:
        v = round(cuota_total / ingreso_neto * 100, 2)
        ap, tol = lim["cuota_ingreso"]
        ratios["cuota_ingreso"] = {"valor_pct": v, "apetito": ap, "tolerancia": tol,
                                   "semaforo": _semaforo(v, ap, tol)}

    # 2) Deuda Total / Excedente (en "veces")
    if excedente > 0:
        v = round(deuda_externa_total / excedente, 2)
        ap, tol = lim["deuda_excedente"]
        ratios["deuda_excedente"] = {"valor_veces": v, "apetito": ap, "tolerancia": tol,
                                     "semaforo": _semaforo(v, ap, tol)}

    # 3) Cuota / Excedente
    if excedente > 0:
        v = round(cuota_total / excedente * 100, 2)
        ap_pair = lim["cuota_excedente"]
        ap = ap_pair[idx_excedente]
        tol = 100 if tipo in ("ME", "PE") else 80
        ratios["cuota_excedente"] = {"valor_pct": v, "apetito": ap, "tolerancia": tol,
                                     "semaforo": _semaforo(v, ap, tol)}

    # 4) N.º de entidades
    if n_entidades is not None:
        ap, tol = LIMITE_ENTIDADES
        ratios["n_entidades"] = {"valor": n_entidades, "apetito": ap, "tolerancia": tol,
                                 "semaforo": _semaforo(n_entidades, ap, tol)}

    # Semáforo global = el peor de todos
    orden = {VERDE: 0, AMARILLO: 1, ROJO: 2}
    peor = VERDE
    for r in ratios.values():
        if orden[r["semaforo"]] > orden[peor]:
            peor = r["semaforo"]

    return {
        "tipo_evaluado": tipo,
        "excedente": round(excedente, 2),
        "cuota_total": round(cuota_total, 2),
        "ratios": ratios,
        "semaforo_global": peor,
        "expuesto_rds": peor == ROJO,
    }
