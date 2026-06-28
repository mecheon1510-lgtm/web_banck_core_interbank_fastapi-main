from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.cfg_database import get_db
from app.repositories import rep_ahorros

router = APIRouter()

@router.get("/resumen-agencia/{codagencia}")
def resumen_agencia(
    codagencia: str,
    periodomes: int = Query(20251231),
    db: Session = Depends(get_db)
):
    rows = rep_ahorros.get_resumen_agencia(db, codagencia, periodomes)
    return [dict(r._mapping) for r in rows]

@router.get("/cliente/{codcliente}")
def cuentas_cliente(
    codcliente: str,
    periodomes: int = Query(20251231),
    db: Session = Depends(get_db)
):
    rows = rep_ahorros.get_cuentas_cliente(db, codcliente, periodomes)
    return [dict(r._mapping) for r in rows]

@router.get("/{codcuentaahorro}")
def detalle(
    codcuentaahorro: str,
    periodomes: int = Query(20251231),
    db: Session = Depends(get_db)
):
    row = rep_ahorros.get_detalle(db, codcuentaahorro, periodomes)
    if not row:
        raise HTTPException(status_code=404, detail="Cuenta de ahorro no encontrada")
    return dict(row._mapping)
