from sqlalchemy import Column, Integer, String, Numeric, Date, SmallInteger, DateTime
from app.core.cfg_database import Base


class DSolicitud(Base):
    """Mapea la tabla existente dsolicitud (núcleo del MPR-003-CRE)."""
    __tablename__ = "dsolicitud"

    pksolicitud            = Column(Integer, primary_key=True, index=True)
    codsolicitud           = Column(String(20), unique=True, nullable=False)
    pkcliente              = Column(Integer)
    codexpediente          = Column(String(30))
    pksolicitudestado      = Column(Integer)      # 1=Eval 2=Aprob 3=Rech 4=Desemb 5=Anul 6=Comité
    pksolicitudsituacion   = Column(Integer)      # 1=Nueva 2=Renov 3=Ampl 4=Refin 5=Reestr
    pkproducto             = Column(Integer)
    pkmodalidad            = Column(Integer)
    pkcanaldesembolso      = Column(Integer)
    pkmoneda               = Column(Integer)
    pknivelaprobacion      = Column(Integer)
    pkcomite               = Column(Integer)
    pkagencia              = Column(Integer)
    pkasesor               = Column(Integer)

    montosolicitudcredito  = Column(Numeric(14, 2))
    nrocuotasolicitud      = Column(Integer)
    plazosolicitudcredito  = Column(Integer)
    fechasolicitudcredito  = Column(Date)

    montoaprobadocredito   = Column(Numeric(14, 2))
    nrocuotaaprobado       = Column(Integer)
    plazoaprobadocredito   = Column(Integer)
    fechaaprobacioncredito = Column(Date)
    tasainterescompensatoria = Column(Numeric(8, 4))

    codtiposolicitud       = Column(String(5))
    destiposolicitud       = Column(String(100))
    codmotivosolicitud     = Column(String(5))
    desmotivosolicitud     = Column(String(200))

    fechahoracreacion        = Column(DateTime)
    fechahoraultmodificacion = Column(DateTime)
    fecultactualizacion      = Column(DateTime)
