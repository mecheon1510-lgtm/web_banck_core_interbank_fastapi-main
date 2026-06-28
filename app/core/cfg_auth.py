"""
Dependencias de autenticación/autorización para FastAPI.

- get_current_user: decodifica el token JWT del header Authorization: Bearer <token>
  y devuelve el payload (sub, pkpersonal, nombre, rol, cargo, codagencia).
- requiere_rol(accion): factory de dependencia que valida, contra la matriz de
  permisos en cfg_roles, si el rol del usuario puede ejecutar la acción.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.cfg_security import decode_token
from app.core.cfg_roles import puede

bearer_scheme = HTTPBearer(auto_error=True)


def get_current_user(
    cred: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    payload = decode_token(cred.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
        )
    return payload


def requiere_rol(accion: str):
    """Devuelve una dependencia que exige permiso para `accion`."""
    def _dep(user: dict = Depends(get_current_user)) -> dict:
        rol = user.get("rol", "")
        if not puede(rol, accion):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"El rol '{rol}' no está autorizado para: {accion}",
            )
        return user
    return _dep
