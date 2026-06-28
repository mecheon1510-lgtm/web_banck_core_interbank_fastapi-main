"""
Rutas del Homebanking (portal del cliente).

Flujo del cliente:
  POST /hb/login           → autenticación del cliente (devuelve token tipo 'cliente')
  GET  /hb/mis-creditos    → créditos del cliente con saldo
  GET  /hb/movimientos     → historial de operaciones (desembolsos, pagos)
  POST /hb/solicitar       → crea una solicitud de crédito (reusa el flujo del core)
  POST /hb/pagar           → paga la próxima cuota de un crédito

El cliente NO es personal: usa su propio token (sub = codcliente, tipo = 'cliente').
"""
import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.cfg_database import get_db
from app.core.cfg_security import create_access_token, decode_token
from app.repositories import rep_homebanking as rephb
from app.controllers import ctl_creditos
from app.schemas.sch_creditos import SolicitudIn

router = APIRouter()
_bearer = HTTPBearer(auto_error=True)


# ---------- esquemas ----------
class HBLoginIn(BaseModel):
    username: str
    password: str


class PagoIn(BaseModel):
    codcuentacredito: str
    monto: float | None = None  # si se omite, paga la cuota completa


# ---------- dependencia de auth del cliente ----------
def cliente_actual(cred: HTTPAuthorizationCredentials = Depends(_bearer)) -> dict:
    payload = decode_token(cred.credentials)
    if not payload or payload.get("tipo") != "cliente":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Token de cliente inválido o expirado")
    return payload


# ---------- endpoints ----------
@router.post("/login")
def login(data: HBLoginIn, db: Session = Depends(get_db)):
    u = rephb.get_usuario(db, data.username)
    if not u:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")
    if (u.activo or "S") != "S" or (u.bloqueado or "N") == "S":
        raise HTTPException(status_code=403, detail="Usuario inactivo o bloqueado")
    try:
        ok = bcrypt.checkpw(data.password.encode()[:72], u.password_hash.encode())
    except Exception:
        ok = False
    if not ok:
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    rephb.registrar_acceso(db, u.pkusuario)
    token = create_access_token({
        "sub": u.codcliente.strip(), "tipo": "cliente",
        "pkcliente": u.pkcliente, "nombre": u.nomcliente,
    })
    return {
        "access_token": token, "token_type": "bearer",
        "codcliente": u.codcliente.strip(), "nombre": u.nomcliente,
    }


@router.get("/mis-creditos")
def mis_creditos(db: Session = Depends(get_db), cli: dict = Depends(cliente_actual)):
    rows = rephb.creditos_cliente(db, cli["pkcliente"])
    return [dict(r._mapping) for r in rows]


@router.get("/movimientos")
def movimientos(limit: int = Query(50, le=200),
                db: Session = Depends(get_db), cli: dict = Depends(cliente_actual)):
    rows = rephb.movimientos(db, cli["pkcliente"], limit)
    return [dict(r._mapping) for r in rows]


@router.post("/solicitar")
def solicitar(data: SolicitudIn, db: Session = Depends(get_db),
              cli: dict = Depends(cliente_actual)):
    """El cliente solicita un crédito desde el portal (entra al flujo del core)."""
    # fuerza el codcliente del token (el cliente solo solicita para sí mismo)
    data.codcliente = cli["sub"]
    res = ctl_creditos.crear_solicitud(db, data, creado_por=f"HB:{cli['sub']}")
    if res.get("error"):
        if res.get("elegibilidad"):
            raise HTTPException(status_code=422, detail=res)
        raise HTTPException(status_code=404, detail=res["error"])
    return res


@router.post("/pagar")
def pagar(data: PagoIn, db: Session = Depends(get_db), cli: dict = Depends(cliente_actual)):
    """Paga la próxima cuota pendiente de un crédito del cliente."""
    cuota = rephb.proxima_cuota(db, data.codcuentacredito)
    if not cuota:
        raise HTTPException(status_code=404, detail="Sin cuotas pendientes para ese crédito")
    monto = data.monto if data.monto is not None else float(cuota.montocuota or 0)
    res = rephb.registrar_pago(db, cuota, monto, cli["pkcliente"])
    return {"codcuentacredito": data.codcuentacredito, **res}
