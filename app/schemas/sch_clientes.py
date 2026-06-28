from pydantic import BaseModel
from typing import Optional
from datetime import date

class ClienteOut(BaseModel):
    pkcliente: int
    codcliente: str
    nomcliente: str
    numerodocumentoidentidad: Optional[str]
    fechanacimiento: Optional[date]
    sexo: Optional[str]
    telefono: Optional[str]
    email: Optional[str]
    montoingresoneto: Optional[float]

    class Config:
        from_attributes = True