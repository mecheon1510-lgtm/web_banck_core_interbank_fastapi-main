# Diagramas UML — Core Financiero Banco Andino (PlantUML)

Diagramas del Core en formato PlantUML (`.puml`), para visualizar en VS Code.

## Cómo verlos en VS Code
1. Instala la extensión **PlantUML** (jebbs.plantuml).
2. Requisitos para renderizar: **Java** + **Graphviz** (dot), o configurar el servidor
   PlantUML remoto en los settings de la extensión (`plantuml.render: PlantUMLServer`).
3. Abre un archivo `.puml` y pulsa **Alt+D** (Preview Current Diagram).
4. Exportar a PNG/SVG: paleta de comandos → "PlantUML: Export Current Diagram".

## Índice de diagramas

| Archivo | Tipo | Qué muestra |
|---|---|---|
| 01_casos_de_uso.puml | Casos de uso | Actores y casos de uso (otorgamiento, HB, recuperaciones, gestión) |
| 02_secuencia_otorgamiento.puml | Secuencia | Flujo end-to-end Homebanking ⇄ Core ⇄ desembolso |
| 03_recuperaciones_estados.puml | Estados | Cobranza: preventiva → temprana → tardía → judicial → castigo |
| 04_componentes_ecosistema.puml | Componentes | 2 backends + 2 frontends + BD compartida |
| 05_core_modelo_datos.puml | Entidad-Relación | Entidades clave del flujo de crédito y recuperaciones |
| 06_actividad_otorgamiento.puml | Actividad | Otorgamiento por rol (MPR-003-CRE) con decisiones |
| 07_estados_solicitud.puml | Estados | Ciclo de vida de la solicitud (En Evaluación → Desembolsado) |
| 08_secuencia_recuperaciones.puml | Secuencia | Recuperaciones: consulta (R1), gestión (R2), transiciones (R3) |
| 09_arquitectura_capas.puml | Paquetes | Arquitectura en capas del backend (rutas→ctl→svc/rep→BD) |

## Relación con la documentación
- Historias de usuario y requisitos: `docs/HISTORIAS_USUARIO_REQUISITOS_CORE.md`
- Ecosistema y roadmap: `ECOSISTEMA_Y_ROADMAP.md`
