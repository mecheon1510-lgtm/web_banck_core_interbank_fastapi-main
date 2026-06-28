"""
Rutas de Recuperaciones / Mora (MPR Recuperación del Crédito).

R1 — Consulta:
  GET  /recuperaciones/resumen          → KPIs de cartera por banda de mora
  GET  /recuperaciones/cartera?banda=   → lista de créditos morosos
R2 — Gestión de cobranza:
  GET  /recuperaciones/tipos-gestion    → catálogo de acciones
  POST /recuperaciones/creditos/{cod}/gestion → registrar acción
  GET  /recuperaciones/creditos/{cod}/gestiones → historial de un crédito
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.cfg_database import get_db
from app.core.cfg_auth import get_current_user, requiere_rol
from app.repositories import rep_recuperaciones as rep

router = APIRouter()


class GestionIn(BaseModel):
    codtipogestion: str            # SMS|LLAM|VISI|CART|COMP|JUDI
    resultado: str = ""
    compromiso_pago: Optional[str] = None   # yyyy-mm-dd
    monto_comprometido: Optional[float] = None


@router.get("/resumen")
def resumen_mora(
    db: Session = Depends(get_db),
    user: dict = Depends(requiere_rol("consultar_mora")),
):
    """KPIs de cartera por banda de mora (preventiva/temprana/tardía/judicial/castigo)."""
    rows = rep.resumen_mora(db)
    items = [dict(r._mapping) for r in rows]
    total = sum(r["n_creditos"] for r in items)
    en_mora = sum(r["n_creditos"] for r in items if r["banda"] != "AL_DIA")
    return {"total": total, "en_mora": en_mora, "por_banda": items}


@router.get("/cartera")
def cartera_mora(
    banda: Optional[str] = Query(None, description="PREVENTIVA|TEMPRANA|TARDIA|JUDICIAL|CASTIGO"),
    limit: int = Query(100, le=300),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: dict = Depends(requiere_rol("consultar_mora")),
):
    """Lista de créditos en mora (filtrable por banda)."""
    rows = rep.cartera_en_mora(db, banda=banda, limit=limit, offset=offset)
    return [dict(r._mapping) for r in rows]


@router.get("/tipos-gestion")
def tipos_gestion(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Catálogo de tipos de gestión de cobranza."""
    return [dict(r._mapping) for r in rep.tipos_gestion(db)]


@router.post("/creditos/{codcuentacredito}/gestion")
def registrar_gestion(
    codcuentacredito: str,
    data: GestionIn,
    db: Session = Depends(get_db),
    user: dict = Depends(requiere_rol("gestionar_cobranza")),
):
    """Registra una acción de cobranza sobre un crédito moroso."""
    res = rep.registrar_gestion(
        db, codcuentacredito, codtipogestion=data.codtipogestion,
        gestor=user.get("sub"), resultado=data.resultado,
        compromiso_pago=data.compromiso_pago, monto_comprometido=data.monto_comprometido)
    if res.get("error"):
        raise HTTPException(status_code=404, detail=res["error"])
    return res


@router.get("/creditos/{codcuentacredito}/gestiones")
def listar_gestiones(
    codcuentacredito: str,
    db: Session = Depends(get_db),
    user: dict = Depends(requiere_rol("consultar_mora")),
):
    """Historial de gestiones de cobranza de un crédito."""
    return [dict(r._mapping) for r in rep.listar_gestiones(db, codcuentacredito)]


# ---------- R3: transiciones de estado ----------

class TransicionIn(BaseModel):
    forzar: bool = False   # permite saltarse el umbral de días (uso excepcional)


@router.post("/creditos/{codcuentacredito}/judicial")
def pasar_judicial(
    codcuentacredito: str,
    data: TransicionIn = TransicionIn(),
    db: Session = Depends(get_db),
    user: dict = Depends(requiere_rol("derivar_judicial")),
):
    """Transición a Cobranza Judicial (>=121 días). P04 del proceso."""
    res = rep.pasar_a_judicial(db, codcuentacredito, gestor=user.get("sub"), forzar=data.forzar)
    if res.get("error"):
        raise HTTPException(status_code=400, detail=res["error"])
    return res


@router.post("/creditos/{codcuentacredito}/castigar")
def castigar(
    codcuentacredito: str,
    data: TransicionIn = TransicionIn(),
    db: Session = Depends(get_db),
    user: dict = Depends(requiere_rol("castigar_credito")),
):
    """Castigo contable del crédito (>180 días). P06 del proceso."""
    res = rep.castigar(db, codcuentacredito, gestor=user.get("sub"), forzar=data.forzar)
    if res.get("error"):
        raise HTTPException(status_code=400, detail=res["error"])
    return res
