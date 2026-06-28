from sqlalchemy.orm import Session
from app.repositories import rep_fag, rep_metas, rep_desembolsos


def get_desembolsos(db: Session, periodomes: int = 202506) -> dict:
    """
    KPIs de desembolsos: volumen del mes y acumulado anual, nro de créditos,
    ticket promedio y desglose por oficina/zona.
    `periodomes` (yyyymm) = mes de la fecha de desembolso.
    """
    anio = str(periodomes)[:4]
    mes = rep_desembolsos.total_mes(db, periodomes)
    anual_rows = rep_desembolsos.total_anual(db, anio)
    anual = anual_rows[0] if anual_rows else None

    return {
        "periodo": periodomes,
        "anio": int(anio),
        "mes": {
            "n_creditos": int(mes.n_creditos or 0),
            "volumen": float(mes.volumen or 0),
            "ticket_promedio": round(float(mes.ticket_promedio or 0), 2),
        },
        "anual": {
            "n_creditos": int(anual.n_creditos or 0) if anual else 0,
            "volumen": float(anual.volumen or 0) if anual else 0.0,
            "ticket_promedio": round(float(anual.ticket_promedio or 0), 2) if anual else 0.0,
        },
        "por_oficina": [
            {
                "codagencia": r.codagencia,
                "desagencia": r.desagencia,
                "codzonacomercial": r.codzonacomercial,
                "deszonacomercial": r.deszonacomercial,
                "n_creditos": int(r.n_creditos or 0),
                "volumen": float(r.volumen or 0),
            }
            for r in rep_desembolsos.por_oficina(db, periodomes)
        ],
        "por_zona": [
            {
                "codzonacomercial": r.codzonacomercial,
                "deszonacomercial": r.deszonacomercial,
                "n_creditos": int(r.n_creditos or 0),
                "volumen": float(r.volumen or 0),
            }
            for r in rep_desembolsos.por_zona(db, periodomes)
        ],
    }

def get_kpis(db: Session, periodomes: int = 202512):
    row = rep_fag.get_kpis_periodo(db, periodomes)
    return {
        "periodo":             periodomes,
        "cartera_total":       float(row.cartera_total or 0),
        "cartera_vigente":     float(row.cartera_vigente or 0),
        "cartera_vencida":     float(row.cartera_vencida or 0),
        "ratio_mora":          float(row.ratio_mora or 0),
        "n_creditos_activos":  int(row.n_creditos or 0),
        "n_clientes_deudores": int(row.n_clientes or 0),
        "captaciones_total":   0,
        "captaciones_ac":      0,
        "captaciones_pf":      0,
        "captaciones_cts":     0,
    }

def get_productividad(db: Session, periodomes: int = 202512,
                       codagencia: str = None):
    rows = rep_metas.get_productividad_asesores(db, periodomes, codagencia)
    resultado = []
    for r in rows:
        meta = float(r.saldocolocaciones_meta or 1)
        real = float(r.saldocolocaciones_real or 0)
        pct  = round(real / meta * 100, 2) if meta > 0 else 0
        semaforo = "VERDE" if pct >= 90 else "AMARILLO" if pct >= 70 else "ROJO"
        resultado.append({
            "codasesor":          r.codasesor,
            "nomasesor":          r.nomasesor,
            "saldo_real":         real,
            "saldo_meta":         meta,
            "cumplimiento_pct":   pct,
            "nroclientes_real":   int(r.nroclientes_real or 0),
            "nroclientes_meta":   int(r.nroclientes_meta or 0),
            "ratiomora_real":     float(r.ratiomora_real or 0),
            "semaforo":           semaforo,
        })
    return resultado
