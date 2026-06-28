from pydantic import BaseModel
from typing import Optional
from datetime import date

class CuentaAhorroOut(BaseModel):
    pkcuentaahorro: int
    codcuentaahorro: str
    nomcliente: str
    tipo_cuenta: str
    montosaldocapitaltotal: Optional[float]
    montosaldointerestotal: Optional[float]
    tasaefectivaanual: Optional[float]
    fechaaperturacuenta: Optional[date]
    # PF
    fechavigencia_pf: Optional[date]
    nrodiasplazofijo_pf: Optional[int]
    montointeresdevengado_pf: Optional[float]

    class Config:
        from_attributes = True