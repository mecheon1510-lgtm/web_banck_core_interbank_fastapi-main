from pydantic import BaseModel
from typing import Optional

class ScoringIn(BaseModel):
    codcliente: str
    montosolicitud: float
    plazo: int                 # meses
    codtipocredito: str        # ME, PE, CO, HI
    montoingresoneto: float
    codactividadeconomica: str
    codasesor: str

class ScoringOut(BaseModel):
    codcliente: str
    score: float               # 0 - 100
    decision: str              # APROBADO / OBSERVADO / RECHAZADO
    tea_sugerida: float        # en porcentaje
    cuota_estimada: float      # S/
    observaciones: list[str]
    detalle_score: dict