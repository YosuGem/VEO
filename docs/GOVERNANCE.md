# Gobernanza de VEO v2

> Las 7 Leyes del Sistema Operativo para Intuicion Social.

## Tabla de Contenidos

1. [Las 7 Leyes](#las-7-leyes)
2. [Contrato de Evolucion Controlada](#contrato-de-evolucion-controlada)
3. [Prohibiciones Permanentes](#prohibiciones-permanentes)
4. [Cambios Permitidos](#cambios-permitidos)
5. [Sistema de Versionado](#sistema-de-versionado)
6. [Regla de Oro](#regla-de-oro)

---

## Las 7 Leyes

### Ley 1: EVIDENCIA ANTES QUE OPINION

> **Ninguna conclusion es valida sin evidencia observable y verificable.**

- Toda hipotesis debe incluir las fuentes que la sustentan
- La evidencia debe ser replicable por terceros
- Los datos anonimos o no verificables se marcan explicitamente como "baja confianza"
- El agente cientifico rechaza automaticamente hipotesis sin evidencia

**Ejemplo de aplicacion**:
```
VEO: "Se detecta aumento del 34% en menciones de 'regulacion IA'"
Evidencia: 12,450 posts analizados, fuentes: Reddit(45%), Twitter(30%), News(25%)
Confianza: 0.85 | Incertidumbre: +/- 0.05
```

### Ley 2: NUNCA EXISTE UNA UNICA EXPLICACION

> **Todo fenomeno observado debe generar al menos 3 hipotesis alternativas.**

- El motor de hipotesis genera automaticamente multiples explicaciones
- Cada hipotesis compite con las demas en el mercado de predicciones
- La confirmacion de una hipotesis no elimina las alternativas
- El sistema reporta siempre: "Hipotesis principal + N alternativas"

**Ejemplo de aplicacion**:
```
H1 (principal): La regulacion de IA se esta acelerando globalmente
H2 (alternativa): Es un efecto de la cobertura mediatica post-evento
H3 (alternativa): Coincidencia temporal de multiples factores independientes
```

### Ley 3: LA INCERTIDUMBRE ES OBLIGATORIA

> **Toda prediccion debe incluir un intervalo de confianza. Predicciones sin incertidumbre son rechazadas.**

- Ninguna prediccion se emite como punto unico (siempre rango)
- El intervalo p5-p95 es obligatorio en toda simulacion Monte Carlo
- Las alertas incluyen: "Probabilidad X% (intervalo Y%-Z%)"
- El sistema nunca dice "va a pasar", dice "hay X% de probabilidad"

**Ejemplo de aplicacion**:
```
ALERTA: Probabilidad de nueva regulacion IA en 6 meses: 72%
Intervalo de confianza: [58%, 84%]
Incertidumbre: ALTA (pocos datos historicos comparables)
```

### Ley 4: LOS SESGOS DEBEN SER EXPLICITOS

> **Todo output del sistema debe incluir los sesgos detectados en el proceso.**

- El agente cientifico detecta sesgos en cada validacion
- Sesgos comunes detectados: confirmacion, disponibilidad, anclaje, grupo
- Los sesgos no invalidan el resultado, pero deben ser conocidos
- Los usuarios pueden ver que sesgos afectan cada conclusion

**Ejemplo de aplicacion**:
```
Hipotesis: Confirmada (confianza 0.75)
Sesgos detectados:
  - sesgo_de_confirmacion: severidad 0.4 (fuentes mayoritariamente pro-regulacion)
  - sesgo_de_disponibilidad: severidad 0.2 (eventos recientes sobreponderados)
Advertencia: Considerar evidencia contraria antes de actuar
```

### Ley 5: LA COMPLEJIDAD DEBE PENALIZARSE

> **Entre dos modelos que explican los mismos datos, se prefiere el mas simple (Ockham).**

- El NEI penaliza automaticamente hipotesis con demasiadas variables
- Los escenarios se limitan a las variables mas relevantes (sensibilidad)
- Los modelos con mas parametros necesitan mas evidencia para ser aceptados
- El sistema prefiere explicaciones directas sobre teorias conspirativas

**Ejemplo de aplicacion**:
```
Modelo A (3 variables): NEI = 0.75
Modelo B (8 variables): NEI = 0.72 (penalizado por complejidad)
Seleccion: Modelo A (mas simple, NEI ajustado mayor)
```

### Ley 6: LA TRAZABILIDAD ES OBLIGATORIA

> **Cada decision del sistema debe poder rastrearse desde la senal de entrada hasta la alerta final.**

- La cadena de auditoria registra cada paso inmutablemente
- Desde una alerta se puede reconstruir: que senal la origino, que hipotesis se genero, que validacion se aplico, que escenario se simulo
- Cada componente firma su contribucion con hash previo
- La auditoria no puede ser modificada ni borrada

**Ejemplo de aplicacion**:
```
ALERTA #2847
  Origen: senal #15,892 (RSS: TechCrunch, 2026-01-15 09:23)
  Hipotesis: hip_4821 (generada por motor, NEI=0.78)
  Validacion: val_2847 (agente cientifico: confirmada)
  Escenario: esc_1047 (Monte Carlo: 5000 runs)
  Prediccion: pred_8391 (probabilidad: 0.82)
  Cadena de auditoria: aud_1 -> aud_2 -> ... -> aud_2847
```

### Ley 7: NINGUN MOTOR ES SAGRADO

> **Todo componente del sistema puede ser cuestionado, desactivado o reemplazado.**

- El agente cientifico puede marcar como "dudoso" el output de cualquier motor
- Los pesos NEI se ajustan automaticamente si un motor falla repetidamente
- El trust score de cada componente es publico y auditable
- Si un motor cae por debajo de cierto trust score, se desactiva automaticamente

**Ejemplo de aplicacion**:
```
Trust Scores (actualizados: 2026-01-15 10:00):
  motor_hipotesis:    0.92 (OK)
  agente_cientifico:  0.88 (OK)
  simulador_mc:       0.75 (OK)
  causal_engine:      0.45 (WARNING - precision baja ultima semana)
  
Accion automatica: causal_engine puesto en modo "observacion"
  (output registrado pero no usado para alertas)
```

---

## Contrato de Evolucion Controlada

VEO v2 evoluciona bajo un contrato estricto:

### Principios de Evolucion

1. **Retrocompatibilidad de datos**: Los datos generados en v2.0 deben ser legibles en v2.x
2. **Gradualidad**: Los cambios se despliegan en fases (canary)
3. **Reversibilidad**: Cualquier cambio puede revertirse sin perdida de datos
4. **Transparencia**: Todos los cambios se registran en CHANGELOG.md y auditoria

### Proceso de Cambio

```
1. Propuesta de cambio (issue)
2. Evaluacion de impacto en las 7 leyes
3. Revision de compatibilidad con datos existentes
4. Implementacion en rama feature/
5. Tests completos pasan
6. Merge a develop -> prueba en test
7. Merge a main -> despliegue gradual
```

---

## Prohibiciones Permanentes

Estos cambios **NUNCA** seran aceptados en VEO:

| # | Prohibicion | Razon |
|---|-------------|-------|
| 1 | Eliminar la trazabilidad | Ley 6 |
| 2 | Emitir predicciones sin incertidumbre | Ley 3 |
| 3 | Permitir una unica hipotesis | Ley 2 |
| 4 | Aceptar evidencia no verificable como valida | Ley 1 |
| 5 | Ocultar sesgos detectados | Ley 4 |
| 6 | Preferir complejidad sobre simplicidad | Ley 5 |
| 7 | Dar privilegio permanente a un motor | Ley 7 |
| 8 | Modificar registros de auditoria | Ley 6 |
| 9 | Permitir acceso directo a la DB sin auditoria | Ley 6 |
| 10 | Eliminar el modo heuristico (sin LLM) | Resiliencia |

---

## Cambios Permitidos

Estos cambios son bienvenidos y se fomentan:

| # | Cambio | Ejemplo |
|---|--------|---------|
| 1 | Nuevas metricas al NEI | Agregar metrica de polarizacion politica |
| 2 | Nuevos metodos de validacion | Test estadistico adicional en agente cientifico |
| 3 | Nuevos tipos de sensores | Conectar nueva fuente de datos (ej: Discord) |
| 4 | Mejoras de performance | Optimizar queries de SQLite |
| 5 | Nuevos comandos Hermes | `hermes export csv` |
| 6 | Mejoras al grafo | Nuevo algoritmo de deteccion de comunidades |
| 7 | Nuevos escenarios | Plantillas predefinidas de simulacion |
| 8 | Mejoras UI/UX | Nuevo panel en dashboard |
| 9 | Documentacion | Mejores ejemplos, tutoriales |
| 10 | Tests adicionales | Mayor cobertura de tests |

---

## Sistema de Versionado

VEO v2 usa **Semantic Versioning** con restricciones adicionales:

### Format: `vMAJOR.MINOR.PATCH`

| Componente | Significado | Ejemplo |
|------------|-------------|---------|
| MAJOR | Cambio que viola compatibilidad de datos | v2 -> v3 |
| MINOR | Nueva funcionalidad, compatible | v2.0 -> v2.1 |
| PATCH | Fix o mejora menor | v2.0.0 -> v2.0.1 |

### Reglas de Versionado

- **v2.0.x**: Versiones de desarrollo activo. Cada release anade correcciones, documentacion o pequenas mejoras.
- **v2.x.0**: Nuevas features mayores (nuevos ciclos, motores, comandos)
- **v2.x.x**: Bug fixes, mejoras de performance, documentacion
- **v3.0.0**: Solo si hay cambio incompatible en esquema de datos

**Version actual:** v2.0.5 (en desarrollo activo)

### Migracion entre Versiones

No existe herramienta automatica de migracion. Entre versiones de la serie v2.0.x:
- Los datos en SQLite son compatibles
- Ejecuta `python cli/hermes_cli.py operations backup` antes de actualizar
- Restaura con `python cli/hermes_cli.py operations restore <id>` si es necesario

---

## Regla de Oro

### Antes de Modificar Cualquier Componente, Responder:

```
1. Este cambio respeta las 7 leyes?     [ ] SI  [ ] NO
2. Mantiene retrocompatibilidad?        [ ] SI  [ ] NO
3. Tiene tests que lo cubren?           [ ] SI  [ ] NO
4. Esta documentado?                    [ ] SI  [ ] NO
5. Puede revertirse facilmente?         [ ] SI  [ ] NO
6. No esta en la lista de prohibidos?   [ ] SI  [ ] NO

Solo si todas las respuestas son SI, proceder.
```

### Checklist de Revision de Cambios

- [ ] Ley 1: El cambio no elimina la evidencia requerida
- [ ] Ley 2: El cambio no impide multiples hipotesis
- [ ] Ley 3: El cambio no elimina intervalos de confianza
- [ ] Ley 4: El cambio no oculta sesgos
- [ ] Ley 5: El cambio no introduce complejidad innecesaria
- [ ] Ley 6: El cambio mantiene trazabilidad
- [ ] Ley 7: El cambio no da privilegios permanentes a ningun motor
- [ ] Tests pasan (>90% cobertura)
- [ ] Documentacion actualizada
- [ ] CHANGELOG.md actualizado
- [ ] Auditoria registra el cambio

---

## Compromiso del Sistema

VEO v2 se compromete a:

1. **Nunca mentir**: Si no sabe algo, lo dice explicitamente
2. **Nunca ocultar**: Toda limitacion es visible
3. **Nunca sobreestimar**: La confianza reportada es conservadora
4. **Siempre mejorar**: Aprende de cada acierto y error
5. **Siempre explicar**: Cada output incluye el razonamiento

> *"El sistema que nunca se equivoca es el sistema que nunca aprende."*
