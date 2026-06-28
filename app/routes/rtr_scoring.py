from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.cfg_database import get_db
from app.schemas.sch_scoring import ScoringIn, ScoringOut
from app.controllers import ctl_scoring

router = APIRouter()

@router.post("/evaluar", response_model=ScoringOut)
def evaluar(data: ScoringIn, db: Session = Depends(get_db)):
    return ctl_scoring.calcular_score(
        codcliente            = data.codcliente,
        montosolicitud        = data.montosolicitud,
        plazo                 = data.plazo,
        codtipocredito        = data.codtipocredito,
        montoingresoneto      = data.montoingresoneto,
        codactividadeconomica = data.codactividadeconomica,
        db                    = db
    )