from sqlalchemy import Column, Integer, String, Numeric, DateTime
from app.core.cfg_database import Base


class DSolicitudEstado(Base):
    __tablename__ = "dsolicitudestado"
    pksolicitudestado  = Column(Integer, primary_key=True)
    codsolicitudestado = Column(String(5))
    dessolicitudestado = Column(String(100))


class DSolicitudSituacion(Base):
    __tablename__ = "dsolicitudsituacion"
    pksolicitudsituacion  = Column(Integer, primary_key=True)
    codsolicitudsituacion = Column(String(5))
    dessolicitudsituacion = Column(String(100))


class DTipoCredito(Base):
    __tablename__ = "dtipocredito"
    pktipocredito  = Column(Integer, primary_key=True)
    codtipocredito = Column(String(5))
    destipocredito = Column(String(100))


class DProducto(Base):
    __tablename__ = "dproducto"
    pkproducto     = Column(Integer, primary_key=True)
    codtipocredito = Column(String(5))
    codproducto    = Column(String(10))
    desproducto    = Column(String(120))


class DModalidad(Base):
    __tablename__ = "dmodalidad"
    pkmodalidad  = Column(Integer, primary_key=True)
    codmodalidad = Column(String(5))
    desmodalidad = Column(String(100))


class DNivelAprobacion(Base):
    __tablename__ = "dnivelaprobacion"
    pknivelaprobacion  = Column(Integer, primary_key=True)
    codnivelaprobacion = Column(String(5))
    desnivelaprobacion = Column(String(120))
    montominimo        = Column(Numeric(16, 4))
    montomaximo        = Column(Numeric(16, 4))


class DComite(Base):
    __tablename__ = "dcomite"
    pkcomite  = Column(Integer, primary_key=True)
    codcomite = Column(String(5))
    descomite = Column(String(100))


class DCalificacionCrediticia(Base):
    __tablename__ = "dcalificacioncrediticia"
    pkcalificacioncrediticia  = Column(Integer, primary_key=True)
    codcalificacioncrediticia = Column(String(5))
    descalificacioncrediticia = Column(String(100))
