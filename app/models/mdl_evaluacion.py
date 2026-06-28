from sqlalchemy import Column, Integer, String, Numeric, DateTime
from app.core.cfg_database import Base


class DEvaluacion(Base):
    """
    Mapea la tabla existente devaluacion (hoy vacía).
    Se usa para persistir el resultado del pre-scoring (actividad 4 del MPR-003-CRE),
    relacionado a la solicitud por codsolicitud.
    """
    __tablename__ = "devaluacion"

    pkevaluacion          = Column(Integer, primary_key=True, index=True)
    nroevaluacion         = Column(String(50))
    valorexcedentecredito = Column(Numeric(16, 4))
    tipoevaluacion        = Column(String(5))
    codsolicitud          = Column(String(20))
    fecultactualizacion   = Column(DateTime)
