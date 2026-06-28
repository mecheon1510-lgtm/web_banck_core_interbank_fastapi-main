from sqlalchemy import Column, String, Date, Numeric, Integer
from app.core.cfg_database import Base

class DCliente(Base):
    __tablename__ = "dcliente"

    pkcliente              = Column(Integer, primary_key=True, index=True)
    codcliente             = Column(String(20), unique=True, nullable=False)
    nomcliente             = Column(String(150), nullable=False)
    numerodocumentoidentidad = Column(String(15))
    fechanacimiento        = Column(Date)
    sexo                   = Column(String(1))
    estadocivil            = Column(String(1))
    telefono               = Column(String(15))
    email                  = Column(String(100))
    montodeingreso         = Column(Numeric(14, 2))
    montoingresoneto       = Column(Numeric(14, 2))
    tipofuenteingreso      = Column(String(5))
    fechaingresocaja       = Column(Date)
