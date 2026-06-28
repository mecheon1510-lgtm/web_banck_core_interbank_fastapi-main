from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.cfg_database import get_db
from app.repositories import rep_clientes
from app.schemas.sch_clientes import ClienteOut

router = APIRouter()

@router.get("/{codcliente}", response_model=ClienteOut)
def get_cliente(codcliente: str, db: Session = Depends(get_db)):
    cliente = rep_clientes.get_by_cod(db, codcliente)
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return cliente
