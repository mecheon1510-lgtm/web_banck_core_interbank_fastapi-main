# Historias de Usuario y Requisitos Funcionales — CORE FINANCIERO Banco Andino

| Campo | Valor |
|---|---|
| **Sistema** | Core Financiero — Banco Andino (CMAC) |
| **Versión doc** | 2.0 |
| **Alcance** | Otorgamiento, evaluación, comité, desembolso, dashboard, bandeja, recuperaciones |
| **Productos** | Empresarial (Microempresa + Pequeña Empresa) y Consumo |
| **Base normativa** | MPR-003-CRE Otorgamiento · Reglamento de Créditos V33 · Política de Créditos V14 · MPR Recuperación del Crédito |
| **Endpoints** | 38 (verificados contra la API viva) |

> Leyenda de estado: ✅ implementado y verificado · 🟡 parcial · ⬜ pendiente.

---

## 1. ACTORES Y ROLES

| Rol (token) | Cargo (dcargopersonal) | Responsabilidad |
|---|---|---|
| **asesor** | Asesor de Negocios | Crea solicitudes, registra ingresos/evaluación, envía a comité, gestiona cobranza |
| **administrador** | Administrador de Agencia | Opinión de viabilidad (≥100k), comité, deriva a judicial |
| **jefe_regional** | Jefe de Negocios Regional | Opinión para montos ≥ S/ 300.000 |
| **riesgos** | Jefe de Riesgos | Opinión de Gerencia de Riesgos |
| **analista** | Analista de Créditos | Opinión de riesgos, consulta de mora |
| **comite** | Funcionario de Créditos | Resuelve (aprueba/deniega), castiga créditos |
| **gerencia** | Gerente | Aprobación de montos altos, transferencia de cartera |
| **cliente** | (titular, vía Homebanking) | Solicita crédito, paga cuotas, consulta |

---

## 2. ÉPICAS, HISTORIAS DE USUARIO Y CRITERIOS DE ACEPTACIÓN

### ÉPICA 1 — Originación y Pre-evaluación

#### HU-01 · Crear solicitud de crédito ✅
> **Como** asesor (o cliente vía Homebanking), **quiero** registrar una solicitud de crédito **para** iniciar el proceso de otorgamiento.

**Requisitos funcionales**
- RF-01.1 Capturar codcliente, monto, plazo, tipo (ME/PE/CO), actividad económica, ingreso neto.
- RF-01.2 Persistir en `dsolicitud` con estado "En Evaluación" (1) y código correlativo `SOLnnnnnnn`.
- RF-01.3 Registrar al creador de la solicitud (trazabilidad por token JWT).

**Criterios de aceptación**
- DADO un cliente válido, CUANDO se envía la solicitud, ENTONCES se crea con estado 1 y devuelve `codsolicitud`, `scoring`, `rds` y `ruta_aprobacion`.
- DADO un cliente inexistente, ENTONCES responde 404.

*Endpoint:* `POST /creditos/solicitudes`

#### HU-02 · Validar elegibilidad (sujeto de crédito) ✅
> **Como** sistema, **quiero** validar que el cliente sea sujeto de crédito (Política 2.3.A) **para** no admitir solicitudes inviables.

- RF-02.1 Rechazar (HTTP 422) si tiene créditos vencidos o en cobranza judicial.
- RF-02.2 Calificación Deficiente/Dudoso/Pérdida ⇒ requiere opinión de Riesgos.
- RF-02.3 Calificación CPP ⇒ admitido con observación.

**Criterio:** DADO un cliente en Pérdida, CUANDO solicita, ENTONCES 422 con el motivo de elegibilidad.

#### HU-03 · Pre-scoring crediticio ✅
> **Como** asesor, **quiero** un score automático **para** priorizar la evaluación.
- RF-03.1 Calcular score 0–100 (capacidad de pago, historial, sector económico, plazo).
- RF-03.2 Devolver decisión (APROBADO/OBSERVADO/RECHAZADO) y TEA sugerida por tipo.

*Endpoint:* `POST /scoring/evaluar` (y embebido en HU-01).

#### HU-04 · Evaluar Riesgo de Sobreendeudamiento (RDS) ✅
> **Como** analista de riesgo, **quiero** los ratios del Art. 13 con semáforo **para** medir el sobreendeudamiento.
- RF-04.1 Calcular cuota/ingreso, deuda/excedente, cuota/excedente.
- RF-04.2 Clasificar cada ratio en VERDE/AMARILLO/ROJO según apetito/tolerancia por tipo de crédito.

---

### ÉPICA 2 — Evaluación de Crédito

#### HU-05 · Registrar fuentes de ingreso ✅
> **Como** asesor, **quiero** registrar los ingresos del cliente (act. 11) **para** sustentar la capacidad de pago.
- RF-05.1 Registrar tipo (negocio/dependiente/RxH) y monto en `fclientefuenteingreso` (upsert por cliente+periodo).

*Endpoint:* `POST /creditos/solicitudes/{cod}/ingresos`

#### HU-06 · Registrar evaluación ✅
> **Como** asesor, **quiero** registrar la evaluación según el tipo (act. 16).
- RF-06.1 Empresarial (ME/PE) → activos del negocio (`fevalmicroactivo`).
- RF-06.2 Consumo (CO) → ingreso vs gasto familiar (`fevalconsumo`).
- RF-06.3 Calcular y persistir el excedente en `devaluacion`.

*Endpoint:* `POST /creditos/solicitudes/{cod}/evaluacion`

---

### ÉPICA 3 — Ruta de Aprobación y Comité

#### HU-07 · Determinar nivel y ruta de aprobación ✅
> **Como** sistema, **quiero** derivar la solicitud al nivel correcto (Art. 30 y 34).
- RF-07.1 Nivel por monto (7 niveles de `dnivelaprobacion`).
- RF-07.2 Opinión Administrador si ≥ S/ 100.000; Jefe Regional si ≥ S/ 300.000.
- RF-07.3 Opinión Riesgos según Art. 34 (monto / 3+ entidades / endeudamiento global).

#### HU-08 · Emitir opiniones ✅
> **Como** administrador/jefe regional/riesgos, **quiero** emitir mi opinión.
- RF-08.1 Registrar opinión favorable/desfavorable con comentario.
- RF-08.2 Opinión de Riesgos desfavorable ⇒ deniega automáticamente.

*Endpoint:* `POST /creditos/solicitudes/{cod}/opinion`

#### HU-09 · Resolución del Comité ✅
> **Como** comité, **quiero** aprobar o denegar la solicitud (act. 42-43).
- RF-09.1 Enviar a comité (estado "En Comité" = 6).
- RF-09.2 Resolver APROBADO / DENEGADO_TEMPORAL / DENEGADO_DEFINITIVO.
- RF-09.3 Regla dura: opinión de Riesgos desfavorable ⇒ ningún comité aprueba (Art. 29.k).

*Endpoints:* `POST .../comite` · `POST .../resolver`

---

### ÉPICA 4 — Desembolso

#### HU-10 · Desembolsar crédito ✅
> **Como** comité/operaciones, **quiero** desembolsar la solicitud aprobada (act. 45-48).
- RF-10.1 Solo si estado = Aprobado (si no, 400).
- RF-10.2 Crear `dcuentacredito` + movimiento de desembolso en `foperaciones`.
- RF-10.3 Cambiar estado a "Desembolsado" (4); impedir re-desembolso.

*Endpoint:* `POST /creditos/solicitudes/{cod}/desembolsar`

#### HU-11 · Generar cronograma referencial ✅
- RF-11.1 Cuota fija (método francés) según monto/plazo/TEA del tipo.

*Endpoint:* `GET /creditos/solicitudes/{cod}/cronograma`

---

### ÉPICA 5 — Gestión, Bandeja y Dashboard

#### HU-12 · Bandeja de solicitudes ✅
> **Como** asesor/comité, **quiero** una bandeja para gestionar solicitudes.
- RF-12.1 Listar con filtros: estado, búsqueda (código/cliente), rango de fechas.
- RF-12.2 Paginación (limit ≤ 200) y contadores por estado.

*Endpoints:* `GET /creditos/solicitudes` · `GET /creditos/solicitudes/resumen`

#### HU-13 · Dashboard institucional ✅
- RF-13.1 KPIs: cartera total/vigente/vencida, ratio de mora.
- RF-13.2 Productividad de asesores vs metas.
- RF-13.3 Desembolsos por mes/año/oficina/zona.
- RF-13.4 Evolución histórica por tipo (ME/PE/CO).

*Endpoints:* `GET /dashboard/kpis · /productividad-asesores · /desembolsos · /evolucion-historica`

#### HU-14 · Mi Cartera (asesor) ✅
- RF-14.1 El asesor ve su cartera automáticamente (pkasesor del token).

*Endpoint:* `GET /creditos/cartera?pkasesor=`

#### HU-15 · Catálogo dinámico de productos ✅
- RF-15.1 Exponer tipos disponibles (ME/PE/CO) agrupados por segmento, leídos de `dproducto`.

*Endpoint:* `GET /creditos/productos`

#### HU-16 · Consulta de crédito y cliente ✅
- RF-16.1 Detalle de un crédito y su cronograma.
- RF-16.2 Ficha del cliente.

*Endpoints:* `GET /creditos/{cod}` · `/creditos/{cod}/cronograma` · `GET /clientes/{cod}`

#### HU-17 · Consulta de ahorros ✅
- RF-17.1 Resumen por agencia, cuentas por cliente, detalle de cuenta.

*Endpoints:* `GET /ahorros/resumen-agencia/{cod}` · `/ahorros/cliente/{cod}` · `/ahorros/{cod}`

---

### ÉPICA 6 — Recuperaciones / Mora

#### HU-18 · Consultar cartera en mora ✅
> **Como** gestor/administrador, **quiero** ver los créditos morosos por banda.
- RF-18.1 KPIs por banda: Preventiva(1-6), Temprana(7-30), Tardía(31-120), Judicial(121-180), Castigo(>180).
- RF-18.2 Listar créditos morosos filtrando por banda.

*Endpoints:* `GET /recuperaciones/resumen` · `/recuperaciones/cartera?banda=`

#### HU-19 · Registrar gestión de cobranza ✅
> **Como** gestor, **quiero** registrar acciones (SMS/llamada/visita/compromiso).
- RF-19.1 Registrar gestión con tipo, resultado, compromiso de pago, monto → `fgestioncobranza`.
- RF-19.2 Consultar historial de gestiones de un crédito.

*Endpoints:* `POST /recuperaciones/creditos/{cod}/gestion` · `GET .../gestiones` · `GET /recuperaciones/tipos-gestion`

#### HU-20 · Derivar a cobranza judicial ✅
> **Como** administrador/gerencia, **quiero** escalar un crédito a judicial.
- RF-20.1 Solo si ≥ 121 días de atraso (400 si no cumple).
- RF-20.2 Marcar flagjudicial, fechaingresojudicial y estado "En Cobranza Judicial".
- RF-20.3 Registrar gestión de trazabilidad automática.

*Endpoint:* `POST /recuperaciones/creditos/{cod}/judicial`

#### HU-21 · Castigar crédito ✅
> **Como** comité/gerencia, **quiero** castigar contablemente un crédito.
- RF-21.1 Solo si > 180 días de atraso.
- RF-21.2 Marcar flagcastigado y estado "Castigado"; registrar trazabilidad.

*Endpoint:* `POST /recuperaciones/creditos/{cod}/castigar`

---

### ÉPICA 7 — Homebanking (canal del cliente)

#### HU-22 · Login del cliente ✅
*Endpoint:* `POST /hb/login`
#### HU-23 · Consultar créditos y movimientos ✅
*Endpoints:* `GET /hb/mis-creditos` · `/hb/movimientos`
#### HU-24 · Solicitar crédito desde el portal ✅
*Endpoint:* `POST /hb/solicitar`
#### HU-25 · Pagar cuota desde el portal ✅
*Endpoint:* `POST /hb/pagar`

---

### ÉPICA 8 — Autenticación y Seguridad

#### HU-26 · Login del personal ✅
- RF-26.1 Autenticación por DNI; JWT con rol, pkasesor, codasesor, codagencia.
- RF-26.2 Credenciales inválidas → 401.

*Endpoint:* `POST /auth/login`

#### HU-27 · Control de acceso por rol (RBAC) ✅
- RF-27.1 Cada acción valida el permiso del rol (matriz `cfg_roles`).
- RF-27.2 Acceso no autorizado → 403; sin token → 401.

---

## 3. REQUISITOS NO FUNCIONALES

| ID | Requisito |
|---|---|
| RNF-1 | **Integridad referencial:** toda operación respeta las FK de la BD. |
| RNF-2 | **Trazabilidad normativa:** cada regla cita su artículo/proceso. |
| RNF-3 | **Seguridad:** JWT en todos los endpoints salvo login; RBAC por rol; bcrypt. |
| RNF-4 | **Consistencia de datos:** calibrados con distribuciones reales (SGN). |
| RNF-5 | **Interoperabilidad:** API REST/JSON; CORS para frontend (5173). |
| RNF-6 | **Datos coherentes:** 2 productos (Empresarial/Consumo), mora realista (~13%). |

---

## 4. MATRIZ DE TRAZABILIDAD HU → ENDPOINT → ESTADO

| HU | Método | Endpoint | Estado |
|---|---|---|---|
| HU-01 | POST | /creditos/solicitudes | ✅ |
| HU-03 | POST | /scoring/evaluar | ✅ |
| HU-05 | POST | /creditos/solicitudes/{cod}/ingresos | ✅ |
| HU-06 | POST | /creditos/solicitudes/{cod}/evaluacion | ✅ |
| HU-08 | POST | /creditos/solicitudes/{cod}/opinion | ✅ |
| HU-09 | POST | /creditos/solicitudes/{cod}/comite, /resolver | ✅ |
| HU-10 | POST | /creditos/solicitudes/{cod}/desembolsar | ✅ |
| HU-11 | GET | /creditos/solicitudes/{cod}/cronograma | ✅ |
| HU-12 | GET | /creditos/solicitudes, /resumen | ✅ |
| HU-13 | GET | /dashboard/kpis, /productividad-asesores, /desembolsos, /evolucion-historica | ✅ |
| HU-14 | GET | /creditos/cartera | ✅ |
| HU-15 | GET | /creditos/productos | ✅ |
| HU-16 | GET | /creditos/{cod}, /creditos/{cod}/cronograma, /clientes/{cod} | ✅ |
| HU-17 | GET | /ahorros/* | ✅ |
| HU-18 | GET | /recuperaciones/resumen, /cartera | ✅ |
| HU-19 | POST/GET | /recuperaciones/creditos/{cod}/gestion, /gestiones, /tipos-gestion | ✅ |
| HU-20 | POST | /recuperaciones/creditos/{cod}/judicial | ✅ |
| HU-21 | POST | /recuperaciones/creditos/{cod}/castigar | ✅ |
| HU-22..25 | — | /hb/* (canal cliente) | ✅ |
| HU-26 | POST | /auth/login | ✅ |
| HU-27 | — | RBAC transversal (cfg_roles) | ✅ |

**Cobertura: 27 historias de usuario · 38 endpoints · 100% verificado contra la API.**
