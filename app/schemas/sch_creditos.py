from pydantic import BaseModel
from typing import Optional
from datetime import date

class CreditoResumenOut(BaseModel):
    pkcuentacredito: int
    codcuentacredito: str
    nomcliente: str
    montosaldocapital: Optional[float]
    diasatrasocredito: Optional[int]
    calificacion: Optional[str]
    car_vig_capital: Optional[float]
    car_ven_capital: Optional[float]

    class Config:
        from_attributes = True

class CronogramaItemOut(BaseModel):
    nrocuota: int
    fechavencimientopagocuota: Optional[date]
    montocuota: Optional[float]
    montocapitalprogramado: Optional[float]
    montointeresprogramado: Optional[float]
    montosaldo: Optional[float]
    codestadocuota: Optional[str]

    class Config:
        from_attributes = True

class SolicitudIn(BaseModel):
    codcliente: str
    montosolicitud: float
    plazo: int
    codtipocredito: str        # ME, PE, CO, HI
    codactividadeconomica: str
    montoingresoneto: float
    codasesor: str
    # --- Datos de centrales de riesgo (no están en la BD del core) ---
    # Opcionales: si se omiten, el ruteo se hace por monto y el RDS se calcula con lo disponible.
    endeudamiento_global: Optional[float] = None      # saldo de deuda en el sistema financiero
    cuotas_sistema_financiero: Optional[float] = None # suma de cuotas mensuales en otras entidades
    n_entidades: Optional[int] = None                 # n.º de entidades (incluida La Caja)
    gastos_familiares: Optional[float] = None          # egresos familiares mensuales (para excedente)
    es_recurrente: bool = False                        # cliente recurrente (afecta límites RDS)


class OpinionIn(BaseModel):
    tipo: str                  # 'admin' | 'jefe_reg' | 'riesgos'
    favorable: bool
    comentario: str = ""


class ComiteIn(BaseModel):
    pkcomite: Optional[int] = None


class ResolucionIn(BaseModel):
    decision: str              # 'APROBADO' | 'DENEGADO_TEMPORAL' | 'DENEGADO_DEFINITIVO'
    motivo: str = ""
    monto_aprobado: Optional[float] = None


class IngresoIn(BaseModel):
    tipo: str                  # 'NE' negocio | 'DE' dependiente | 'RH' rec. honorarios
    monto: float
    nombre_empresa: Optional[str] = None


class EvaluacionIn(BaseModel):
    ingreso: float
    gasto_familiar: float
    fortaleza: str = ""
    debilidad: str = ""