"""
Controlador del flujo de Otorgamiento de Créditos — MPR-003-CRE (Sección I).

Orquesta: crear solicitud (act.13/16) + pre-scoring (act.4) -> ruta de aprobación
por monto/endeudamiento (act.22) -> opiniones (act.23-36) -> comité (act.41) ->
resolución (act.42-43) -> cronograma referencial (act.45).
"""
from sqlalchemy.orm import Session

from app.controllers import ctl_scoring
from app.repositories import rep_clientes, rep_solicitudes as repsol, rep_evaluacion
from app.services import svc_elegibilidad, svc_rds

# Umbrales del Reglamento de Créditos V33 (Art. 34, 32, 29.i), en Soles
UMBRAL_OPINION_ADMIN   = 100_000   # Art. 29.i / 34: >= requiere opinión Administrador + Riesgos
UMBRAL_OPINION_JEFEREG = 300_000   # Art. 32: >= requiere opinión Jefe de Negocios Regional (Formato 04)
UMBRAL_RIESGOS_GENERAL = 100_000   # Art. 34: monto propuesto >= 100k -> Riesgos
UMBRAL_ME_CO_RIESGOS   = 50_000    # Art. 34: ME/Consumo >= 50k con 3+ entidades -> Riesgos
UMBRAL_PROPUESTA_MIN   = 15_000    # Art. 34: y propuesta > 15k (regla de endeudamiento global)


def determinar_ruta(monto: float, codtipocredito: str,
                    endeudamiento_global: float | None = None,
                    n_entidades: int | None = None,
                    requiere_riesgos_por_calificacion: bool = False) -> dict:
    """
    Ruta de aprobación según Reglamento Art. 34 (opinión de Riesgos) y Art. 30 (nivel por monto).

    - Opinión de Administrador: monto propuesto >= S/ 100 000 (Art. 29.i).
    - Opinión de Jefe Regional: monto propuesto >= S/ 300 000 (Art. 32).
    - Opinión de Riesgos (Art. 34), si CUALQUIERA:
        * monto propuesto >= 100 000;
        * ME/CO con monto >= 50 000 y 3+ entidades;
        * endeudamiento global >= 100k (o >=50k ME/CO con 3+ entidades) y propuesta > 15 000;
        * o lo exige la calificación del cliente (Def/Dud/Pérdida).
    """
    es_me_co = codtipocredito in ("ME", "CO")
    tres_o_mas = (n_entidades is not None and n_entidades >= 3)

    requiere_admin    = monto >= UMBRAL_OPINION_ADMIN
    requiere_jefe_reg = monto >= UMBRAL_OPINION_JEFEREG

    # Reglas de Art. 34 para opinión de Riesgos
    r1 = monto >= UMBRAL_RIESGOS_GENERAL
    r2 = es_me_co and monto >= UMBRAL_ME_CO_RIESGOS and tres_o_mas
    r3 = False
    if endeudamiento_global is not None and monto > UMBRAL_PROPUESTA_MIN:
        if endeudamiento_global >= UMBRAL_RIESGOS_GENERAL:
            r3 = True
        elif es_me_co and endeudamiento_global >= UMBRAL_ME_CO_RIESGOS and tres_o_mas:
            r3 = True
    requiere_riesgos = r1 or r2 or r3 or requiere_riesgos_por_calificacion

    pasos = []
    if requiere_admin:
        pasos.append("opinion_admin")          # Formato 03
    if requiere_jefe_reg:
        pasos.append("opinion_jefe_reg")       # Formato 04
    if requiere_riesgos:
        pasos.append("opinion_riesgos")        # Formato 02 / SISTRA
    pasos.append("comite")                     # siempre pasa por comité

    return {
        "monto_propuesto": float(monto),
        "endeudamiento_global": endeudamiento_global,
        "requiere_opinion_admin": requiere_admin,
        "requiere_opinion_jefe_regional": requiere_jefe_reg,
        "requiere_opinion_riesgos": requiere_riesgos,
        "riesgos_por_calificacion": requiere_riesgos_por_calificacion,
        "pasos": pasos,
    }


def crear_solicitud(db: Session, data, creado_por: str | None = None) -> dict:
    """
    Actividad 13/16 + pre-scoring (act. 4).
    `data` es un sch_creditos.SolicitudIn.
    `creado_por` = codpersonal del usuario autenticado (para trazabilidad).

    Nota: dsolicitud.pkasesor es FK a dasesor, mientras que el token identifica al
    usuario por pkpersonal (FK a dpersonal). La BD no tiene mapeo persona->asesor,
    por eso el creador se registra en el motivo (traza) y pkasesor usa el default.
    """
    cliente = rep_clientes.get_by_cod(db, data.codcliente)
    if not cliente:
        return {"error": "Cliente no encontrado", "codcliente": data.codcliente}

    # 1) Elegibilidad — ¿es sujeto de crédito? (Política 2.3.A)
    elegib = svc_elegibilidad.evaluar(db, cliente.pkcliente)
    if elegib["resultado"] == svc_elegibilidad.NO_APTO:
        return {"error": "Cliente no es sujeto de crédito",
                "elegibilidad": elegib}

    # 2) Pre-scoring (reutiliza el motor existente)
    scoring = ctl_scoring.calcular_score(
        codcliente            = data.codcliente,
        montosolicitud        = data.montosolicitud,
        plazo                 = data.plazo,
        codtipocredito        = data.codtipocredito,
        montoingresoneto      = data.montoingresoneto,
        codactividadeconomica = data.codactividadeconomica,
        db                    = db,
    )

    # 3) RDS — ratios de sobreendeudamiento (Art. 13)
    cuota = float(scoring.get("cuota_estimada") or 0)
    rds = svc_rds.evaluar(
        codtipocredito=data.codtipocredito,
        cuota_propuesta=cuota,
        ingreso_neto=data.montoingresoneto,
        cuotas_sistema_financiero=getattr(data, "cuotas_sistema_financiero", None) or 0.0,
        deuda_externa_total=getattr(data, "endeudamiento_global", None) or 0.0,
        gastos_familiares=getattr(data, "gastos_familiares", None) or 0.0,
        n_entidades=getattr(data, "n_entidades", None),
        es_recurrente=getattr(data, "es_recurrente", False),
    )

    # 4) Ruta de aprobación (Art. 34 + Art. 30)
    endeud = getattr(data, "endeudamiento_global", None)
    n_ent = getattr(data, "n_entidades", None)
    ruta = determinar_ruta(
        data.montosolicitud, data.codtipocredito,
        endeudamiento_global=endeud, n_entidades=n_ent,
        requiere_riesgos_por_calificacion=elegib.get("requiere_opinion_riesgos", False),
    )
    nivel = repsol.nivel_por_monto(db, data.montosolicitud)
    pknivel = nivel.pknivelaprobacion if nivel else None

    # Motivo con traza: creador + observación CPP si aplica (no hay estado "Observado"
    # en dsolicitudestado, por eso la observación va en el motivo y en la respuesta).
    observado = elegib.get("observado", False)
    partes = ["Nueva solicitud (MPR-003-CRE)"]
    if creado_por:
        partes.append(f"creada por {creado_por}")
    if observado:
        partes.append("OBSERVADA: cliente CPP, requiere justificación")
    motivo = " | ".join(partes)

    # Persistir la solicitud en estado 'En Evaluación' (act. 13).
    creada = repsol.crear(
        db,
        pkcliente=cliente.pkcliente,
        pkasesor=None,
        monto=data.montosolicitud,
        plazo=data.plazo,
        nrocuotas=data.plazo,
        codtipocredito=data.codtipocredito,
        pknivelaprobacion=pknivel,
        motivo=motivo,
    )

    return {
        "codsolicitud": creada["codsolicitud"],
        "estado": "En Evaluación",
        "observada": observado,
        "creado_por": creado_por,
        "elegibilidad": elegib,
        "scoring": scoring,
        "rds": rds,
        "nivel_aprobacion": {
            "codigo": nivel.codnivelaprobacion if nivel else None,
            "descripcion": nivel.desnivelaprobacion if nivel else None,
        },
        "ruta_aprobacion": ruta,
    }


def registrar_opinion(db: Session, codsolicitud: str, *, tipo: str,
                      favorable: bool, comentario: str = "") -> dict:
    """
    Actividades 23-36: opinión de Administrador / Jefe Regional / Gerencia de Riesgos.
    Si la opinión de Riesgos es desfavorable -> deniega (act. 34).
    """
    sol = repsol.obtener(db, codsolicitud)
    if not sol:
        return {"error": "Solicitud no encontrada"}

    if tipo == "riesgos" and not favorable:
        repsol.cambiar_estado(db, codsolicitud, repsol.ESTADO_RECHAZADO,
                              motivo=f"Riesgos desfavorable: {comentario}")
        return {"codsolicitud": codsolicitud, "resultado": "RECHAZADO por Riesgos",
                "estado": "Rechazado"}

    return {"codsolicitud": codsolicitud, "opinion": tipo,
            "favorable": favorable, "comentario": comentario,
            "estado": sol.dessolicitudestado}


def enviar_a_comite(db: Session, codsolicitud: str, pkcomite: int | None = None) -> dict:
    """Actividad 41: pre-aprueba y presenta al Comité (estado 06)."""
    sol = repsol.obtener(db, codsolicitud)
    if not sol:
        return {"error": "Solicitud no encontrada"}
    repsol.cambiar_estado(db, codsolicitud, repsol.ESTADO_EN_COMITE,
                          pkcomite=pkcomite)
    return {"codsolicitud": codsolicitud, "estado": "En Comité"}


def resolver(db: Session, codsolicitud: str, *, decision: str,
             motivo: str = "", monto_aprobado: float | None = None) -> dict:
    """
    Actividad 42-43: resolución del Comité.
    decision: 'APROBADO' | 'DENEGADO_TEMPORAL' | 'DENEGADO_DEFINITIVO'.
    """
    sol = repsol.obtener(db, codsolicitud)
    if not sol:
        return {"error": "Solicitud no encontrada"}

    if decision == "APROBADO":
        monto = monto_aprobado if monto_aprobado is not None else float(sol.montosolicitudcredito or 0)
        repsol.cambiar_estado(db, codsolicitud, repsol.ESTADO_APROBADO,
                              motivo=motivo or "Aprobado por Comité",
                              monto_aprobado=monto)
        return {"codsolicitud": codsolicitud, "estado": "Aprobado",
                "monto_aprobado": monto}
    else:
        repsol.cambiar_estado(db, codsolicitud, repsol.ESTADO_RECHAZADO,
                              motivo=f"{decision}: {motivo}")
        return {"codsolicitud": codsolicitud, "estado": "Rechazado",
                "decision": decision, "motivo": motivo}


def registrar_ingreso(db: Session, codsolicitud: str, *, tipo: str, monto: float,
                      nombre_empresa: str = None) -> dict:
    """Actividad 11: el asesor registra una fuente de ingreso del cliente."""
    sol = repsol.obtener(db, codsolicitud)
    if not sol:
        return {"error": "Solicitud no encontrada"}
    res = rep_evaluacion.registrar_ingreso(db, sol.pkcliente, tipo=tipo, monto=monto,
                                           nombre_empresa=nombre_empresa)
    return {"codsolicitud": codsolicitud, **res}


def registrar_evaluacion(db: Session, codsolicitud: str, *, ingreso: float,
                         gasto_familiar: float, fortaleza: str = "",
                         debilidad: str = "") -> dict:
    """Actividad 16: el asesor registra la evaluación (cabecera + detalle ME/CO)."""
    sol = repsol.obtener(db, codsolicitud)
    if not sol:
        return {"error": "Solicitud no encontrada"}
    es_me = (sol.codtiposolicitud or "").strip() in ("ME", "01")
    return rep_evaluacion.registrar_evaluacion(
        db, codsolicitud, es_microempresa=es_me, ingreso=ingreso,
        gasto_familiar=gasto_familiar, monto_solicitud=float(sol.montosolicitudcredito or 0),
        fortaleza=fortaleza, debilidad=debilidad)


def desembolsar(db: Session, codsolicitud: str) -> dict:
    """Actividades 45-48: desembolsa una solicitud APROBADA (crea cuenta + movimiento)."""
    sol = repsol.obtener(db, codsolicitud)
    if not sol:
        return {"error": "Solicitud no encontrada"}
    if sol.pksolicitudestado != repsol.ESTADO_APROBADO:
        return {"error": "La solicitud no está aprobada", "estado": sol.dessolicitudestado}
    
    try:
        res = rep_evaluacion.desembolsar(db, sol)
    except ValueError as e:
        # Si hay error lógico en el desembolso (p.ej., sin cuenta de ahorro), retornar con error claro
        db.rollback()  # Deshacer cambios
        return {"error": f"No se pudo procesar el desembolso: {str(e)}", "codsolicitud": codsolicitud}
    except Exception as e:
        # Cualquier otro error (SQL, etc.)
        db.rollback()  # Deshacer cambios
        import traceback
        print(f"ERROR en desembolso: {str(e)}")
        print(traceback.format_exc())
        return {"error": f"Error inesperado en desembolso: {str(e)}", "codsolicitud": codsolicitud}
    
    try:
        repsol.cambiar_estado(db, codsolicitud, repsol.ESTADO_DESEMBOLSADO,
                              motivo="Desembolsado vía core")
    except Exception as e:
        db.rollback()
        return {"error": f"Error al cambiar estado: {str(e)}", "codsolicitud": codsolicitud}
    
    return {"codsolicitud": codsolicitud, "estado": "Desembolsado", **res}


def generar_cronograma(db: Session, codsolicitud: str) -> dict:
    """
    Actividad 45: plan de pagos referencial (cuota fija francesa) a partir
    del monto aprobado y la TEA sugerida por el historial crediticio del cliente.
    """
    sol = repsol.obtener(db, codsolicitud)
    if not sol:
        return {"error": "Solicitud no encontrada"}
    if sol.pksolicitudestado != repsol.ESTADO_APROBADO:
        return {"error": "La solicitud no está aprobada", "estado": sol.dessolicitudestado}

    cliente = rep_clientes.get_by_cod(db, sol.codcliente)
    if not cliente:
        return {"error": "Cliente asociado no encontrado"}

    monto = float(sol.montoaprobadocredito or sol.montosolicitudcredito or 0)
    plazo = int(sol.plazosolicitudcredito or sol.nrocuotasolicitud or 12)
    if monto <= 0 or plazo <= 0:
        return {"error": "Monto o plazo inválido para generar el cronograma"}

    # Determinar TEA según calificación crediticia real (historial) del cliente.
    elegibilidad = svc_elegibilidad.evaluar(db, cliente.pkcliente)
    calificacion = elegibilidad.get("calificacion", "SIN_HISTORIAL")

    if calificacion == "Normal":
        tea = 14.0
    elif calificacion == "CPP":
        tea = 28.5
    elif calificacion == "SIN_HISTORIAL":
        tea = 28.5
    else:
        tea = 45.0

    DESGRAVAMEN_MENSUAL_FRACT = 0.00085  # 0.085% mensual
    tem = (1 + tea / 100) ** (1 / 12) - 1
    cuota_base = monto * tem * (1 + tem) ** plazo / ((1 + tem) ** plazo - 1) if tem > 0 else monto / plazo

    saldo = monto
    cuotas = []
    for n in range(1, plazo + 1):
        interes = saldo * tem
        desgravamen = saldo * DESGRAVAMEN_MENSUAL_FRACT
        capital = cuota_base - interes
        cuota_total_mes = cuota_base + desgravamen
        saldo = max(0.0, saldo - capital)
        cuotas.append({
            "nrocuota": n,
            "cuota_base": round(cuota_base, 2),
            "capital": round(capital, 2),
            "interes": round(interes, 2),
            "desgravamen": round(desgravamen, 2),
            "cuota_total": round(cuota_total_mes, 2),
            "saldo": round(saldo, 2),
        })

    return {
        "codsolicitud": codsolicitud,
        "monto": round(monto, 2),
        "plazo_meses": plazo,
        "tea_aplicada": tea,
        "tasa_desgravamen": "0.085%",
        "cronograma": cuotas,
    }
