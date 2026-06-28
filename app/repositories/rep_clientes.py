from sqlalchemy.orm import Session
from app.models.mdl_clientes import DCliente

def get_by_cod(db: Session, codcliente: str):
    return db.query(DCliente).filter(
        DCliente.codcliente == codcliente
    ).first()

def get_by_dni(db: Session, dni: str):
    return db.query(DCliente).filter(
        DCliente.numerodocumentoidentidad == dni
    ).first()

def get_all(db: Session, skip: int = 0, limit: int = 50):
    return db.query(DCliente).offset(skip).limit(limit).all()