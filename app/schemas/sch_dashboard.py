from pydantic import BaseModel
from typing import List

class KPIsOut(BaseModel):
    periodo: int
    cartera_total: float
    cartera_vigente: float
    cartera_vencida: float
    ratio_mora: float
    captaciones_total: float
    captaciones_ac: float
    captaciones_pf: float
    captaciones_cts: float
    n_creditos_activos: int
    n_clientes_deudores: int

class ProductividadAsesorOut(BaseModel):
    codasesor: str
    nomasesor: str
    saldo_real: float
    saldo_meta: float
    cumplimiento_pct: float
    nroclientes_real: int
    nroclientes_meta: int
    ratiomora_real: float
    semaforo: str              # VERDE / AMARILLO / ROJO

class EvolucionHistoricaOut(BaseModel):
    periodo: int
    tipo_credito: str
    saldo_real: float
    saldo_meta: float
    ratiomora_real: float