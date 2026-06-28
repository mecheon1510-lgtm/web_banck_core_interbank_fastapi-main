"""
Parámetros de calibración para el generador de datos sintéticos.

Fuente: datos REALES de scoring de Caja Huancayo (Tesis SGN, 2015):
  - PostEvaluationMicroPequenia.xlsx (135.367 créditos micro/pequeña)
  - PostEvaluationConsumo.xlsx       (177.822 créditos de consumo)

Estos valores reflejan distribuciones reales del portafolio, para que los datos
generados en bd_core_financiero sean estadísticamente realistas.

NOTA sobre la tasa: TasaInteres en los datos es % MENSUAL (TEM).
  TEM mediana ≈ 2.5-2.9% → TEA ≈ (1+TEM)^12 - 1 ≈ 34-41%. Coherente con micro/consumo.
"""

# Mix de calificación RCC (cod 0=Normal,1=CPP,2=Deficiente,3=Dudoso,4=Pérdida)
# Combinado de micro y consumo (≈ promedio ponderado).
CALIFICACION_RCC = {
    "0": 0.826,   # Normal
    "1": 0.032,   # CPP
    "2": 0.015,   # Deficiente
    "3": 0.017,   # Dudoso
    "4": 0.110,   # Pérdida
}

# Probabilidad de estar expuesto a RDS (riesgo de sobreendeudamiento)
RDS_EXPUESTO = 0.037   # ~3.7% marcado 'S'

# Distribución del nº de entidades en el sistema financiero (RCC)
# media ≈ 1.7, mediana 1, p75 = 2, máx ~13
NUM_ENTIDADES = {"media": 1.7, "p25": 1, "p50": 1, "p75": 2, "max": 13}

# Moneda: casi todo Soles
PROB_MONEDA_SOLES = 0.999

# Parámetros por tipo de crédito (montos en soles, tasa = TEM %)
CALIBRACION_TIPO = {
    "ME": {  # Microempresa
        "peso": 0.88,                 # 88% de la cartera micro/peq
        "monto": {"p25": 1000, "p50": 3000, "p75": 6000, "media": 6604, "max": 50000},
        "tem_pct": {"p25": 1.5, "p50": 2.5, "p75": 3.5, "media": 2.63},
        "mora_max": {"p50": 3, "p75": 8, "media": 14.7},
    },
    "PE": {  # Pequeña empresa
        "peso": 0.12,
        "monto": {"p25": 5000, "p50": 12000, "p75": 30000, "media": 25000, "max": 300000},
        "tem_pct": {"p25": 1.4, "p50": 2.2, "p75": 3.0, "media": 2.3},
        "mora_max": {"p50": 2, "p75": 7, "media": 12},
    },
    "CO": {  # Consumo
        "peso": 1.0,                  # (segmento aparte)
        "monto": {"p25": 1000, "p50": 1500, "p75": 3000, "media": 2882, "max": 50000},
        "tem_pct": {"p25": 1.6, "p50": 2.9, "p75": 3.7, "media": 2.71},
        "mora_max": {"p50": 2, "p75": 11, "media": 18},
    },
}

# Mora máxima esperada por banda de calificación (días) — coherente con SBS y los datos:
#   Normal 0 / CPP 9-30 / Deficiente 31-90 / Dudoso 91-180 / Pérdida >180
MORA_POR_CALIFICACION = {
    "0": (0, 0),
    "1": (9, 30),
    "2": (31, 90),
    "3": (91, 180),
    "4": (181, 1672),
}
