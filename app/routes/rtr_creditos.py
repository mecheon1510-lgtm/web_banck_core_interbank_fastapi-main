from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.cfg_database import get_db
from app.core.cfg_auth import get_current_user, requiere_rol
from app.core.cfg_roles import puede
from app.controllers import ctl_creditos
from app.repositories import rep_creditos, rep_solicitudes
from app.schemas.sch_creditos import (
    SolicitudIn, OpinionIn, ComiteIn, ResolucionIn, IngresoIn, EvaluacionIn,
)

router = APIRouter()

# ───────────────────────── Flujo MPR-003-CRE (Sección I) ─────────────────────
# IMPORTANTE: estas rutas van ANTES del comodín GET /{codcuentacredito}.

@router.post("/solicitudes")
def crear_solicitud(
    data: SolicitudIn,
    db: Session = Depends(get_db),
    user: dict = Depends(requiere_rol("crear_solicitud")),
):
    """Actividad 13/16 + pre-scoring (act. 4). Crea la solicitud en estado En Evaluación."""
    res = ctl_creditos.crear_solicitud(db, data, creado_por=user.get("sub"))
    if res.get("error"):
        # 422 cuando el cliente existe pero no es sujeto de crédito; 404 si no existe
        if res.get("elegibilidad"):
            raise HTTPException(status_code=422, detail=res)
        raise HTTPException(status_code=404, detail=res["error"])
    return res


@router.get("/solicitudes")
def listar_solicitudes(
    estado: Optional[int] = Query(None, description="pksolicitudestado: 1 Eval, 2 Aprob, 3 Rech, 6 Comité"),
    search: Optional[str] = Query(None, description="código de solicitud o nombre de cliente"),
    fec_ini: Optional[str] = Query(None, description="fecha inicial yyyy-mm-dd"),
    fec_fin: Optional[str] = Query(None, description="fecha final yyyy-mm-dd"),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Bandeja de trabajo: listado de solicitudes con filtros opcionales (solo lectura)."""
    rows = rep_solicitudes.listar(db, estado=estado, search=search,
                                  fec_ini=fec_ini, fec_fin=fec_fin,
                                  limit=limit, offset=offset)
    return [dict(r._mapping) for r in rows]


@router.get("/solicitudes/resumen")
def resumen_solicitudes(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Contadores de solicitudes por estado (KPIs institucionales, solo lectura)."""
    rows = rep_solicitudes.resumen(db)
    por_estado = [dict(r._mapping) for r in rows]
    total = sum(r["n"] for r in por_estado)
    return {"total": total, "por_estado": por_estado}


@router.get("/solicitudes/{codsolicitud}")
def detalle_solicitud(
    codsolicitud: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    row = rep_solicitudes.obtener(db, codsolicitud)
    if not row:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    return dict(row._mapping)


@router.post("/solicitudes/{codsolicitud}/opinion")
def opinion(
    codsolicitud: str,
    data: OpinionIn,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Actividades 23-36. El permiso depende del tipo de opinión."""
    accion = {"admin": "opinion_admin",
              "jefe_reg": "opinion_jefe_reg",
              "riesgos": "opinion_riesgos"}.get(data.tipo)
    if not accion or not puede(user.get("rol", ""), accion):
        raise HTTPException(status_code=403,
                            detail=f"El rol '{user.get('rol')}' no puede emitir opinión '{data.tipo}'")
    res = ctl_creditos.registrar_opinion(
        db, codsolicitud, tipo=data.tipo,
        favorable=data.favorable, comentario=data.comentario)
    if res.get("error"):
        raise HTTPException(status_code=404, detail=res["error"])
    return res


@router.post("/solicitudes/{codsolicitud}/comite")
def enviar_comite(
    codsolicitud: str,
    data: ComiteIn,
    db: Session = Depends(get_db),
    user: dict = Depends(requiere_rol("enviar_comite")),
):
    """Actividad 41: presenta la propuesta al Comité (estado En Comité)."""
    res = ctl_creditos.enviar_a_comite(db, codsolicitud, pkcomite=data.pkcomite)
    if res.get("error"):
        raise HTTPException(status_code=404, detail=res["error"])
    return res


@router.post("/solicitudes/{codsolicitud}/resolver")
def resolver(
    codsolicitud: str,
    data: ResolucionIn,
    db: Session = Depends(get_db),
    user: dict = Depends(requiere_rol("resolver_comite")),
):
    """Actividad 42-43: resolución del Comité (aprobado/denegado)."""
    res = ctl_creditos.resolver(
        db, codsolicitud, decision=data.decision,
        motivo=data.motivo, monto_aprobado=data.monto_aprobado)
    if res.get("error"):
        raise HTTPException(status_code=400, detail=res["error"])
    return res


@router.get("/solicitudes/{codsolicitud}/cronograma")
def cronograma_solicitud(
    codsolicitud: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Actividad 45: plan de pagos referencial."""
    res = ctl_creditos.generar_cronograma(db, codsolicitud)
    if res.get("error"):
        raise HTTPException(status_code=400, detail=res["error"])
    return res


@router.post("/solicitudes/{codsolicitud}/ingresos")
def registrar_ingresos(
    codsolicitud: str,
    data: IngresoIn,
    db: Session = Depends(get_db),
    user: dict = Depends(requiere_rol("crear_solicitud")),
):
    """Actividad 11: el asesor registra una fuente de ingreso del cliente."""
    res = ctl_creditos.registrar_ingreso(db, codsolicitud, tipo=data.tipo,
                                         monto=data.monto, nombre_empresa=data.nombre_empresa)
    if res.get("error"):
        raise HTTPException(status_code=404, detail=res["error"])
    return res


@router.post("/solicitudes/{codsolicitud}/evaluacion")
def registrar_evaluacion(
    codsolicitud: str,
    data: EvaluacionIn,
    db: Session = Depends(get_db),
    user: dict = Depends(requiere_rol("crear_solicitud")),
):
    """Actividad 16: el asesor registra la evaluación (cabecera + detalle ME/CO)."""
    res = ctl_creditos.registrar_evaluacion(db, codsolicitud, ingreso=data.ingreso,
                                            gasto_familiar=data.gasto_familiar,
                                            fortaleza=data.fortaleza, debilidad=data.debilidad)
    if res.get("error"):
        raise HTTPException(status_code=404, detail=res["error"])
    return res


@router.post("/solicitudes/{codsolicitud}/desembolsar")
def desembolsar(
    codsolicitud: str,
    db: Session = Depends(get_db),
    user: dict = Depends(requiere_rol("resolver_comite")),
):
    """Actividades 45-48: desembolsa una solicitud aprobada (crea cuenta + movimiento)."""
    res = ctl_creditos.desembolsar(db, codsolicitud)
    if res.get("error"):
        raise HTTPException(status_code=400, detail=res["error"])
    return res


# ───────────────────────── Catálogo de productos ─────────────────────────────

@router.get("/productos")
def productos_disponibles(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    Tipos de crédito disponibles para que el frontend los liste dinámicamente.
    Devuelve los códigos funcionales (ME/PE/CO) agrupados por segmento
    (Empresarial / Consumo). Si en el futuro cambia dproducto, esto se refleja solo.
    """
    rows = rep_creditos.get_productos_disponibles(db)
    items = []
    for r in rows:
        cod = rep_creditos.map_tipo_func(r.codtipocredito)
        items.append({
            "codtipocredito": cod,                       # ME | PE | CO
            "descripcion": (r.destipocredito or "").strip(),
            "segmento": rep_creditos.segmento_de(cod),    # EMPRESARIAL | CONSUMO
        })
    # agrupado por segmento para conveniencia del front
    segmentos = {}
    for it in items:
        segmentos.setdefault(it["segmento"], []).append(it)
    return {"productos": items, "por_segmento": segmentos}


# ───────────────────────── Consultas de cartera (existentes) ─────────────────

@router.get("/cartera")
def cartera(
    pkasesor: int = Query(..., description="PK del asesor autenticado"),
    periodomes: int = Query(202512),
    db: Session = Depends(get_db),
):
    rows = rep_creditos.get_cartera_asesor(db, pkasesor, periodomes)
    return [dict(r._mapping) for r in rows]


@router.get("/{codcuentacredito}")
def detalle(codcuentacredito: str, db: Session = Depends(get_db)):
    row = rep_creditos.get_detalle(db, codcuentacredito)
    if not row:
        raise HTTPException(status_code=404, detail="Crédito no encontrado")
    return dict(row._mapping)


@router.get("/{codcuentacredito}/cronograma")
def cronograma(codcuentacredito: str, db: Session = Depends(get_db)):
    rows = rep_creditos.get_cronograma(db, codcuentacredito)
    return [dict(r._mapping) for r in rows]
