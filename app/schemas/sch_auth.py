from pydantic import BaseModel
from typing import Optional

class LoginIn(BaseModel):
    numerodni: str
    password: str

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    codpersonal: str
    nombre: str
    rol: str
    codagencia: str
    pkasesor: Optional[int] = None   # PK del asesor (None si el usuario no es asesor)
    codasesor: Optional[str] = None