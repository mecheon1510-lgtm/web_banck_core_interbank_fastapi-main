"""
Validación complementaria del core: Scoring + Ciclo de vida + módulo Recuperaciones
(R1 consulta, R2 gestión, R3 transiciones) con RBAC. Contra la API viva en :8001.
Uso:  ./venv/Scripts/python.exe scripts/validar_recuperaciones.py
"""
import sys
import httpx

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE = "http://localhost:8001"
USERS = {
    "asesor": "11111111", "administrador": "11111112",
    "comite": "11111115", "gerencia": None,
}
passed = failed = 0
notes = []

def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1; print(f"  [PASS] {name}" + (f"  ({detail})" if detail else ""))
    else:
        failed += 1; print(f"  [FAIL] {name}" + (f"  ({detail})" if detail else ""))

def section(t): print(f"\n=== {t} ===")

c = httpx.Client(base_url=BASE, timeout=25.0)

def login(rol):
    dni = USERS[rol]
    return c.post("/auth/login", json={"numerodni": dni, "password": dni}).json()

def H(info): return {"Authorization": f"Bearer {info['access_token']}"}
def det(r):
    try: return r.json().get("detail")
    except Exception: return r.text[:80]

admin = login("administrador"); HA = H(admin)
comite = login("comite"); HC = H(comite)
asesor = login("asesor"); HS = H(asesor)

# codcliente real (la cartera no lo expone; lo tomamos del listado de solicitudes)
lst = c.get("/creditos/solicitudes", params={"limit": 10}, headers=HA).json()
cod_cli = next(((r.get("codcliente") or "").strip() for r in lst if r.get("codcliente")), None)

# ───────────────────────── Scoring ME/PE/CO ─────────────────────────
section("Motor de scoring (ME/PE/CO)")
if cod_cli:
    ases = admin.get("codasesor") or "AS0036"
    for tipo in ("ME", "PE", "CO"):
        p = {"codcliente": cod_cli, "montosolicitud": 8000, "plazo": 12, "codtipocredito": tipo,
             "montoingresoneto": 3000, "codactividadeconomica": "4711", "codasesor": ases}
        r = c.post("/scoring/evaluar", json=p, headers=HA); sc = r.json() if r.status_code == 200 else {}
        ok = r.status_code == 200 and 0 <= float(sc.get("score", -1)) <= 100 and sc.get("decision") in {"APROBADO","OBSERVADO","RECHAZADO"}
        check(f"scoring {tipo}", ok, f"score={sc.get('score')} dec={sc.get('decision')} tea={sc.get('tea_sugerida')}")
else:
    notes.append("Sin codcliente: scoring/ciclo omitidos.")

# ───────────────────────── Ciclo de vida ────────────────────────────
section("Ciclo de vida solicitud (crear→ingresos→evaluación→comité→resolver→desembolsar)")
if cod_cli:
    ases = admin.get("codasesor") or "AS0036"
    r = c.post("/creditos/solicitudes", headers=HA, json={
        "codcliente": cod_cli, "montosolicitud": 6000, "plazo": 12, "codtipocredito": "CO",
        "codactividadeconomica": "4711", "montoingresoneto": 3500, "codasesor": ases, "gastos_familiares": 1000})
    if r.status_code == 200:
        sc = r.json()["codsolicitud"]; check("crear solicitud", True, sc)
        check("registrar ingresos", c.post(f"/creditos/solicitudes/{sc}/ingresos", headers=HA,
              json={"tipo": "DE", "monto": 3500}).status_code == 200)
        re = c.post(f"/creditos/solicitudes/{sc}/evaluacion", headers=HA, json={"ingreso": 3500, "gasto_familiar": 1000})
        check("registrar evaluación", re.status_code == 200, f"excedente={re.json().get('excedente') if re.status_code==200 else re.status_code}")
        check("enviar a comité", c.post(f"/creditos/solicitudes/{sc}/comite", headers=HA, json={"pkcomite": None}).status_code == 200)
        check("resolver APROBADO (comité)", c.post(f"/creditos/solicitudes/{sc}/resolver", headers=HC,
              json={"decision": "APROBADO", "motivo": "val", "monto_aprobado": 6000}).status_code == 200)
        rd = c.post(f"/creditos/solicitudes/{sc}/desembolsar", headers=HA)
        crd = rd.json().get("codcuentacredito") if rd.status_code == 200 else None
        check("desembolsar → cuenta CRD", rd.status_code == 200 and bool(crd), f"crd={crd}")
    elif r.status_code == 422:
        check("crear solicitud → 422 (elegibilidad)", True, "cliente no sujeto de crédito"); notes.append("Ciclo omitido (422).")
    else:
        check("crear solicitud", False, f"HTTP {r.status_code}")

# ───────────────────────── R1: Recuperaciones (consulta) ────────────
section("Recuperaciones R1 — consulta")
r = c.get("/recuperaciones/resumen", headers=HA); res = r.json() if r.status_code == 200 else {}
check("GET /recuperaciones/resumen 200", r.status_code == 200)
if res:
    en_mora_calc = sum(b["n_creditos"] for b in res["por_banda"] if b["banda"] != "AL_DIA")
    check("en_mora == suma bandas != AL_DIA", res["en_mora"] == en_mora_calc, f"en_mora={res['en_mora']} calc={en_mora_calc}")
    bandas = {b["banda"] for b in res["por_banda"]}
    check("bandas válidas", bandas.issubset({"AL_DIA","PREVENTIVA","TEMPRANA","TARDIA","JUDICIAL","CASTIGO"}), f"{sorted(bandas)}")
    saldo_ok = all(b["saldo_vencido"] <= b["saldo"] + 0.01 for b in res["por_banda"])
    check("saldo_vencido <= saldo en cada banda", saldo_ok)
r = c.get("/recuperaciones/cartera", params={"banda": "TEMPRANA", "limit": 5}, headers=HA)
cart = r.json() if r.status_code == 200 else []
check("GET /recuperaciones/cartera?banda=TEMPRANA", r.status_code == 200 and isinstance(cart, list), f"n={len(cart)}")
check("todos los de la banda filtrada son TEMPRANA", all(x["banda"] == "TEMPRANA" for x in cart) if cart else True)
r = c.get("/recuperaciones/cartera", params={"limit": 400}, headers=HA)
check("cartera limit>300 -> 422 (validación)", r.status_code == 422, f"HTTP {r.status_code}")

# RBAC consulta: asesor sí, sin token no
check("asesor consultar_mora -> 200", c.get("/recuperaciones/resumen", headers=HS).status_code == 200)
check("sin token -> 401/403", c.get("/recuperaciones/resumen").status_code in (401, 403))

# ───────────────────────── R2: gestión de cobranza ──────────────────
section("Recuperaciones R2 — gestión de cobranza")
tipos = c.get("/recuperaciones/tipos-gestion", headers=HA).json()
check("tipos-gestion (SMS/LLAM/VISI/CART/COMP/JUDI)",
      {"SMS","LLAM","VISI","CART","COMP","JUDI"} == {t["codtipogestion"] for t in tipos}, f"n={len(tipos)}")
# un crédito moroso cualquiera
moroso = c.get("/recuperaciones/cartera", params={"banda": "TEMPRANA", "limit": 1}, headers=HA).json()
if moroso:
    cod = moroso[0]["codcuentacredito"]
    antes = len(c.get(f"/recuperaciones/creditos/{cod}/gestiones", headers=HA).json())
    r = c.post(f"/recuperaciones/creditos/{cod}/gestion", headers=HA,
               json={"codtipogestion": "LLAM", "resultado": "validación", "compromiso_pago": "2026-07-01", "monto_comprometido": 300})
    check("registrar gestión (admin)", r.status_code == 200 and "pkgestion" in r.json(), f"HTTP {r.status_code}")
    desp = c.get(f"/recuperaciones/creditos/{cod}/gestiones", headers=HA).json()
    check("gestión aparece en historial", len(desp) == antes + 1, f"{antes}->{len(desp)}")
    # RBAC: asesor sí gestiona; comité no (gestionar_cobranza = asesor/administrador)
    check("asesor gestionar -> 200", c.post(f"/recuperaciones/creditos/{cod}/gestion", headers=HS,
          json={"codtipogestion": "SMS"}).status_code == 200)
    check("comité gestionar -> 403", c.post(f"/recuperaciones/creditos/{cod}/gestion", headers=HC,
          json={"codtipogestion": "SMS"}).status_code == 403)

# ───────────────────────── R3: transiciones de estado ───────────────
section("Recuperaciones R3 — transiciones (judicial / castigo) + umbrales + RBAC")
def candidato(banda, flag):
    rows = c.get("/recuperaciones/cartera", params={"banda": banda, "limit": 60}, headers=HA).json()
    return next((x for x in rows if x[flag] != "S"), None)

# JUDICIAL: 400 umbral (TARDIA <121), 400 ya-judicial, 200 happy (>=121)
tardia = c.get("/recuperaciones/cartera", params={"banda": "TARDIA", "limit": 60}, headers=HA).json()
bajo = next((x for x in tardia if x["diasatrasocredito"] < 121 and x["flagjudicial"] != "S"), None)
if bajo:
    r = c.post(f"/recuperaciones/creditos/{bajo['codcuentacredito']}/judicial", headers=HA, json={"forzar": False})
    check("judicial <121 -> 400 umbral", r.status_code == 400 and "umbral" in str(det(r)).lower(), f'detail="{det(r)}"')
ya_jud = next((x for x in c.get("/recuperaciones/cartera", params={"banda": "JUDICIAL", "limit": 60}, headers=HA).json() if x["flagjudicial"] == "S"), None)
if ya_jud:
    r = c.post(f"/recuperaciones/creditos/{ya_jud['codcuentacredito']}/judicial", headers=HA, json={"forzar": False})
    check("judicial ya-en-estado -> 400", r.status_code == 400, f'detail="{det(r)}"')
cand_jud = candidato("JUDICIAL", "flagjudicial")
if cand_jud:
    r = c.post(f"/recuperaciones/creditos/{cand_jud['codcuentacredito']}/judicial", headers=HA, json={"forzar": False})
    g = r.json() if r.status_code == 200 else {}
    check("admin derivar judicial (>=121) -> 200", r.status_code == 200 and g.get("estado") == "En Cobranza Judicial",
          f"{cand_jud['codcuentacredito']} dias={g.get('dias_atraso')}")

# CASTIGO happy (>180) con comité
cand_cas = candidato("CASTIGO", "flagcastigado")
if cand_cas:
    r = c.post(f"/recuperaciones/creditos/{cand_cas['codcuentacredito']}/castigar", headers=HC, json={"forzar": False})
    g = r.json() if r.status_code == 200 else {}
    check("comité castigar (>180) -> 200", r.status_code == 200 and g.get("estado") == "Castigado",
          f"{cand_cas['codcuentacredito']} dias={g.get('dias_atraso')}")
    # confirma badge flagcastigado=S
    row = next((x for x in c.get("/recuperaciones/cartera", params={"banda": "CASTIGO", "limit": 300}, headers=HA).json()
                if x["codcuentacredito"] == cand_cas["codcuentacredito"]), None)
    check("flagcastigado=S tras refrescar", bool(row) and row["flagcastigado"] == "S")

# RBAC transiciones
any_cas = c.get("/recuperaciones/cartera", params={"banda": "CASTIGO", "limit": 1}, headers=HA).json()
if any_cas:
    cc = any_cas[0]["codcuentacredito"]
    check("admin castigar -> 403 (no castigar_credito)", c.post(f"/recuperaciones/creditos/{cc}/castigar", headers=HA, json={"forzar": False}).status_code == 403)
    check("comité judicial -> 403 (no derivar_judicial)", c.post(f"/recuperaciones/creditos/{cc}/judicial", headers=HC, json={"forzar": False}).status_code == 403)
    check("asesor judicial -> 403", c.post(f"/recuperaciones/creditos/{cc}/judicial", headers=HS, json={"forzar": False}).status_code == 403)
    check("asesor castigar -> 403", c.post(f"/recuperaciones/creditos/{cc}/castigar", headers=HS, json={"forzar": False}).status_code == 403)

print("\n" + "=" * 60)
print(f"RESULTADO: {passed} PASS / {failed} FAIL")
for n in notes: print(f"  nota: {n}")
print("=" * 60)
c.close()
sys.exit(1 if failed else 0)
