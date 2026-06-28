"""
Validación funcional del core (backend) contra la API viva en :8001.
Ejercita todos los routers, valida consistencia de datos y RBAC.
Uso:  ./venv/Scripts/python.exe scripts/validar_core.py
"""
import sys
import httpx

BASE = "http://localhost:8001"
USERS = {
    "asesor":        "11111111",
    "administrador": "11111112",
    "jefe_regional": "11111113",
    "riesgos":       "11111114",
    "comite":        "11111115",
    "analista":      "11111116",
}

passed = 0
failed = 0
notes = []

def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  [PASS] {name}" + (f"  ({detail})" if detail else ""))
    else:
        failed += 1
        print(f"  [FAIL] {name}" + (f"  ({detail})" if detail else ""))

def section(t):
    print(f"\n=== {t} ===")

cli = httpx.Client(base_url=BASE, timeout=20.0)

def login(rol):
    dni = USERS[rol]
    r = cli.post("/auth/login", json={"numerodni": dni, "password": dni})
    r.raise_for_status()
    return r.json()["access_token"], r.json()

def H(tok):
    return {"Authorization": f"Bearer {tok}"}

# ───────────────────────── 1. Health + Auth ─────────────────────────
section("1. Health + Autenticación")
r = cli.get("/")
check("GET / responde 200 + status ok", r.status_code == 200 and r.json().get("status") == "ok")

tok_admin, info_admin = login("administrador")
check("login administrador (11111112)", info_admin["rol"] == "administrador", f"rol={info_admin['rol']}")
tok_comite, _ = login("comite")
tok_asesor, info_ase = login("asesor")
check("login asesor pkasesor presente", info_ase.get("pkasesor") is not None, f"pkasesor={info_ase.get('pkasesor')}")

r = cli.post("/auth/login", json={"numerodni": "11111112", "password": "CLAVE_MALA"})
check("password incorrecta -> 401", r.status_code == 401, f"HTTP {r.status_code}")
r = cli.post("/auth/login", json={"numerodni": "00000000", "password": "00000000"})
check("DNI inexistente -> 401", r.status_code == 401, f"HTTP {r.status_code}")

# ───────────────────────── 2. Catálogo de productos (2 productos) ────
section("2. Catálogo de productos (alineación 2 productos)")
r = cli.get("/creditos/productos", headers=H(tok_admin))
if r.status_code == 200:
    body = r.json()
    cods = sorted({p["codtipocredito"] for p in body.get("productos", [])})
    segs = sorted(body.get("por_segmento", {}).keys())
    check("GET /creditos/productos 200", True)
    check("solo codigos ME/PE/CO", set(cods).issubset({"ME", "PE", "CO"}) and len(cods) > 0, f"cods={cods}")
    check("sin HI/MD/GE en catalogo", not ({"HI", "MD", "GE"} & set(cods)), f"cods={cods}")
    check("segmentos EMPRESARIAL/CONSUMO", set(segs).issubset({"EMPRESARIAL", "CONSUMO"}), f"segmentos={segs}")
else:
    check("GET /creditos/productos 200", False, f"HTTP {r.status_code}")

# ───────────────────────── 3. Dashboard + consistencia ──────────────
section("3. Dashboard institucional + consistencia de datos")
r = cli.get("/dashboard/kpis", params={"periodomes": 202512}, headers=H(tok_admin))
k = r.json() if r.status_code == 200 else {}
check("GET /dashboard/kpis 200", r.status_code == 200)
if k:
    total = float(k["cartera_total"]); vig = float(k["cartera_vigente"]); ven = float(k["cartera_vencida"])
    ratio = float(k["ratio_mora"])
    check("vigente + vencida ~= total", abs((vig + ven) - total) <= max(1.0, total * 0.005),
          f"vig+ven={vig+ven:.2f} total={total:.2f}")
    check("ratio_mora ~= vencida/total*100", abs(ratio - (ven / total * 100)) <= 0.1,
          f"ratio={ratio:.2f} calc={(ven/total*100):.2f}")
    check("ratio_mora realista ~13% (>10, <20)", 10 < ratio < 20, f"ratio={ratio:.2f}%")
    check("n_creditos_activos > 0", int(k["n_creditos_activos"]) > 0, f"n={k['n_creditos_activos']}")

r = cli.get("/dashboard/evolucion-historica", headers=H(tok_admin))
ev = r.json() if r.status_code == 200 else []
check("GET /dashboard/evolucion-historica no vacio", r.status_code == 200 and len(ev) > 0, f"filas={len(ev)}")
tipos_hist = sorted({str(x.get("codtipocredito")) for x in ev}) if ev else []
check("historico solo tipos ME/PE/CO", set(tipos_hist).issubset({"ME", "PE", "CO"}) if tipos_hist else True, f"tipos={tipos_hist}")

r = cli.get("/dashboard/desembolsos", params={"periodomes": 202506}, headers=H(tok_admin))
d = r.json() if r.status_code == 200 else {}
check("GET /dashboard/desembolsos contrato", all(x in d for x in ("mes", "anual", "por_oficina", "por_zona")) if d else False)

r = cli.get("/dashboard/productividad-asesores", params={"periodomes": 202512}, headers=H(tok_admin))
check("GET /dashboard/productividad-asesores 200 lista", r.status_code == 200 and isinstance(r.json(), list))

# ───────────────────────── 4. Cartera + Clientes ────────────────────
section("4. Cartera del asesor + Clientes")
pkasesor = info_admin["pkasesor"]
r = cli.get("/creditos/cartera", params={"pkasesor": pkasesor, "periodomes": 202512}, headers=H(tok_admin))
cartera = r.json() if r.status_code == 200 else []
check("GET /creditos/cartera 200 lista", r.status_code == 200 and isinstance(cartera, list), f"n={len(cartera)}")
r = cli.get("/creditos/cartera", headers=H(tok_admin))  # falta pkasesor obligatorio
check("cartera sin pkasesor -> 422 (validacion)", r.status_code == 422, f"HTTP {r.status_code}")

cod_cli = None
if cartera:
    sample = cartera[0]
    cod_cli = (sample.get("codcliente") or "").strip() or None
    check("cada credito trae calificacion", all("calificacion" in c for c in cartera[:20]))

# Cliente: tomamos un codcliente conocido de la cartera
if cod_cli:
    r = cli.get(f"/clientes/{cod_cli}", headers=H(tok_admin))
    check(f"GET /clientes/{cod_cli} 200", r.status_code == 200, f"HTTP {r.status_code}")
r = cli.get("/clientes/CLI999999", headers=H(tok_admin))
check("cliente inexistente -> 404", r.status_code == 404, f"HTTP {r.status_code}")

# ───────────────────────── 5. Solicitudes (lectura) ─────────────────
section("5. Solicitudes - lectura y ruteo de rutas")
r = cli.get("/creditos/solicitudes/resumen", headers=H(tok_admin))
res = r.json() if r.status_code == 200 else {}
check("GET /solicitudes/resumen (no lo traga el comodin /{cod})", r.status_code == 200 and "por_estado" in res)
r = cli.get("/creditos/solicitudes", params={"estado": 1, "limit": 5}, headers=H(tok_admin))
lst = r.json() if r.status_code == 200 else []
check("GET /solicitudes?estado=1 lista", r.status_code == 200 and isinstance(lst, list), f"n={len(lst)}")
if lst:
    cods_sol = lst[0]["codsolicitud"]
    r = cli.get(f"/creditos/solicitudes/{cods_sol}", headers=H(tok_admin))
    check(f"GET detalle {cods_sol} 200", r.status_code == 200)
r = cli.get("/creditos/solicitudes/SOL9999999", headers=H(tok_admin))
check("solicitud inexistente -> 404", r.status_code == 404, f"HTTP {r.status_code}")

# ───────────────────────── 6. Scoring ME/PE/CO ──────────────────────
section("6. Motor de scoring (ME/PE/CO)")
if cod_cli:
    for tipo in ("ME", "PE", "CO"):
        payload = {
            "codcliente": cod_cli, "montosolicitud": 8000, "plazo": 12,
            "codtipocredito": tipo, "montoingresoneto": 3000,
            "codactividadeconomica": "4711", "codasesor": info_admin.get("codasesor") or "AS0036",
        }
        r = cli.post("/scoring/evaluar", json=payload, headers=H(tok_admin))
        ok = r.status_code == 200
        sc = r.json() if ok else {}
        cond = ok and 0 <= float(sc.get("score", -1)) <= 100 and sc.get("decision") in {"APROBADO", "OBSERVADO", "RECHAZADO"}
        check(f"scoring tipo {tipo}", cond, f"HTTP {r.status_code} score={sc.get('score')} dec={sc.get('decision')}")
else:
    notes.append("Sin codcliente de cartera: se omitio scoring.")

# ───────────────────────── 7. RBAC (permisos por rol) ───────────────
section("7. Control de acceso por rol (RBAC)")
# asesor NO puede resolver/desembolsar (resolver_comite)
r = cli.post("/creditos/solicitudes/SOL0000001/desembolsar", headers=H(tok_asesor))
check("asesor desembolsar -> 403", r.status_code == 403, f"HTTP {r.status_code}")
# asesor NO puede emitir opinion 'admin'
r = cli.post("/creditos/solicitudes/SOL0000001/opinion", headers=H(tok_asesor),
             json={"tipo": "admin", "favorable": True, "comentario": "x"})
check("asesor opinion admin -> 403", r.status_code == 403, f"HTTP {r.status_code}")
# comite NO puede crear_solicitud
r = cli.post("/creditos/solicitudes", headers=H(tok_comite),
             json={"codcliente": cod_cli or "CLI000001", "montosolicitud": 5000, "plazo": 12,
                   "codtipocredito": "CO", "codactividadeconomica": "4711",
                   "montoingresoneto": 2500, "codasesor": "AS0040"})
check("comite crear_solicitud -> 403", r.status_code == 403, f"HTTP {r.status_code}")
# sin token -> 401/403
r = cli.get("/creditos/solicitudes/resumen")
check("sin token en endpoint protegido -> 401/403", r.status_code in (401, 403), f"HTTP {r.status_code}")

# ───────────────────────── 8. Ahorros ───────────────────────────────
section("8. Ahorros (captaciones)")
r = cli.get("/ahorros/resumen-agencia/0001", params={"periodomes": 20251231}, headers=H(tok_admin))
check("GET /ahorros/resumen-agencia/0001 200 lista", r.status_code == 200 and isinstance(r.json(), list), f"n={len(r.json()) if r.status_code==200 else '-'}")

# ───────────────────────── 9. Ciclo de vida (best-effort) ───────────
section("9. Ciclo de vida solicitud (crear->ingresos->evaluacion->comite->resolver->desembolsar)")
ciclo_cod = None
if cod_cli:
    r = cli.post("/creditos/solicitudes", headers=H(tok_admin),
                 json={"codcliente": cod_cli, "montosolicitud": 6000, "plazo": 12,
                       "codtipocredito": "CO", "codactividadeconomica": "4711",
                       "montoingresoneto": 3500, "codasesor": info_admin.get("codasesor") or "AS0036",
                       "gastos_familiares": 1000})
    if r.status_code == 200:
        ciclo_cod = r.json().get("codsolicitud")
        check("crear solicitud (admin)", bool(ciclo_cod), f"cod={ciclo_cod}")
    elif r.status_code == 422:
        check("crear solicitud -> 422 (elegibilidad funcionando)", True, "cliente no sujeto de credito")
        notes.append(f"Ciclo omitido: cliente {cod_cli} no es sujeto de credito (422).")
    else:
        check("crear solicitud", False, f"HTTP {r.status_code} {r.text[:120]}")

if ciclo_cod:
    r = cli.post(f"/creditos/solicitudes/{ciclo_cod}/ingresos", headers=H(tok_admin),
                 json={"tipo": "DE", "monto": 3500, "nombre_empresa": "Validacion SAC"})
    check("registrar ingresos", r.status_code == 200, f"HTTP {r.status_code}")
    r = cli.post(f"/creditos/solicitudes/{ciclo_cod}/evaluacion", headers=H(tok_admin),
                 json={"ingreso": 3500, "gasto_familiar": 1000, "fortaleza": "ok", "debilidad": "-"})
    ev_ok = r.status_code == 200
    check("registrar evaluacion (excedente)", ev_ok, f"HTTP {r.status_code} {r.json() if ev_ok else r.text[:80]}")
    r = cli.post(f"/creditos/solicitudes/{ciclo_cod}/comite", headers=H(tok_admin), json={"pkcomite": None})
    check("enviar a comite", r.status_code == 200, f"HTTP {r.status_code}")
    # resolver con usuario comite
    r = cli.post(f"/creditos/solicitudes/{ciclo_cod}/resolver", headers=H(tok_comite),
                 json={"decision": "APROBADO", "motivo": "validacion", "monto_aprobado": 6000})
    check("resolver APROBADO (comite)", r.status_code == 200, f"HTTP {r.status_code} {r.text[:100]}")
    # desembolsar
    r = cli.post(f"/creditos/solicitudes/{ciclo_cod}/desembolsar", headers=H(tok_admin))
    des_ok = r.status_code == 200
    crd = r.json().get("codcuentacredito") if des_ok else None
    check("desembolsar -> crea cuenta CRD", des_ok and bool(crd), f"HTTP {r.status_code} crd={crd}")
    # estado final = Desembolsado
    r = cli.get(f"/creditos/solicitudes/{ciclo_cod}", headers=H(tok_admin))
    if r.status_code == 200:
        check("estado final = Desembolsado (4)", r.json().get("pksolicitudestado") == 4,
              f"estado={r.json().get('pksolicitudestado')}")
    # re-desembolsar -> 400
    r = cli.post(f"/creditos/solicitudes/{ciclo_cod}/desembolsar", headers=H(tok_admin))
    check("re-desembolsar -> 400 no aprobada", r.status_code == 400, f"HTTP {r.status_code}")

# ───────────────────────── Resumen ──────────────────────────────────
print("\n" + "=" * 60)
print(f"RESULTADO: {passed} PASS / {failed} FAIL")
for n in notes:
    print(f"  nota: {n}")
print("=" * 60)
cli.close()
sys.exit(1 if failed else 0)
