from fastapi import APIRouter, Depends, Query
from typing import Optional
from sqlalchemy.orm import Session
from app.core.cfg_database import get_db
from app.controllers import ctl_dashboard
from app.repositories import rep_metas

router = APIRouter()

@router.get("/kpis")
def kpis(
    periodomes: int = Query(202512),
    db: Session = Depends(get_db)
):
    return ctl_dashboard.get_kpis(db, periodomes)

@router.get("/productividad-asesores")
def productividad(
    periodomes: int = Query(202512),
    codagencia: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    return ctl_dashboard.get_productividad(db, periodomes, codagencia)

@router.get("/evolucion-historica")
def evolucion(db: Session = Depends(get_db)):
    rows = rep_metas.get_evolucion_historica(db)
    return [dict(r._mapping) for r in rows]

@router.get("/desembolsos")
def desembolsos(
    periodomes: int = Query(202506, description="yyyymm: mes de la fecha de desembolso"),
    db: Session = Depends(get_db)
):
    return ctl_dashboard.get_desembolsos(db, periodomes)
