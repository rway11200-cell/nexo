## Sistema de presupuesto en tiempo real — ingesta HTTP + Notion + Fosforito

### Estado: ✅ COMPLETADO

### Arquitectura final

```
Tasker (Android) → HTTP GET → Railway (budget-webhook) → Notion DB Movimientos → Telegram group "Presupuesto CorJar"
```

### Enlaces

- **Webhook URL:** https://budget-webhook-production.up.railway.app
- **GitHub repo:** https://github.com/rway11200-cell/budget-webhook
- **Notion DB Movimientos (Seba Personal):** https://app.notion.com/p/2d8065894ee5809d920fe252d20d3d8c
- **Notion DB Periodo (presupuesto mensual):** https://app.notion.com/p/39d065894ee58036a3efc73eadeae4f8
- **Telegram group:** "Presupuesto CorJar" (ID: -1004337757506)
- **Bot Fosforito:** @hermes_asistente_seba_bot (ID: 8721430395)

### Endpoints disponibles

| Endpoint | Método | Qué hace |
|---|---|---|
| `/tasker` | GET | Detecta automáticamente CMR o Scotia |
| `/tasker/cmr` | GET | Solo compras CMR (Banco Falabella) |
| `/tasker/scotiabank` | GET | Solo pagos Scotia |
| `/` | GET | Health check: `{"status": "ok"}` |
| `/test-telegram` | GET | Envía mensaje de test al grupo |

Todos reciben `?text=...` con el texto de la notificación bancaria.

### Variables de entorno (Railway)

| Variable | Valor | Descripción |
|---|---|---|
| `NOTION_API_TOKEN` | `ntn_F17034...` | Token integración "Hermes" (workspace Seba Personal) |
| `MOVIMIENTOS_DB` | `2d806589-4ee5-809d-920f-e252d20d3d8c` | Database ID de "Movimientos" |
| `TELEGRAM_BOT_TOKEN` | `8721430395:...` | Token de Fosforito |
| `TELEGRAM_GROUP_ID` | `-1004337757506` | Chat ID del grupo "Presupuesto CorJar" |
| `PORT` | `8080` | Puerto Railway |

### Parseo de notificaciones

**CMR (Banco Falabella):**
```
Compraste $X.XXX en MERCHANT ... SANTIAGO/CHL ... Con tu CMR ...
```

**Scotia (Scotiabank):**
```
App Scotia. Se realizó un pago ... por $X.XXX en MERCHANT.
```

### Registro en Notion

La DB "Movimientos" recibe:
- **Nombre:** Comercio + `[CMR]` o `[Scotia]`
- **Monto:** Número entero
- **Categoría:** Inferida por keywords (comida, salud, transporte, auto, perritos, vestuario, suscripciones, otro)
- **Fecha:** Fecha actual
- **Periodo:** Relation a página activa de DB "Periodo"

### Presupuesto dinámico

El webhook lee el presupuesto desde la DB **"Periodo"** en Notion:
- Busca la página con `Activo = true` (ej: "Julio 2026")
- Lee el campo `Presupuesto` (número)
- Calcula: `Presupuesto - SUM(Monto de gastos con Periodo relation)`
- Responde en Telegram con el saldo disponible

### Tasker

**Perfil activo:** Notification → Owner Application: "Banco Falabella" → Title: `Compraste*`
**Acción:** HTTP GET → `https://budget-webhook-production.up.railway.app/tasker?text=%NTITLE%20%NTEXT`

### Historial de fixes importantes

1. **Force push** para eliminar hardcoded values del git history
2. **Campo "Categoría"** (con acento) vs "Categoria" — error 400
3. **Parent type:** `data_source_id` → `database_id` con Notion-Version 2022-06-28
4. **Nombres de campos:** `Name` → `Nombre`, `$` → `Monto`
5. **Periodo relation:** Usar `databases/` endpoint en vez de `data_sources/`
6. **Placeholders Tasker:** Limpieza de `%evtprm`, `%20`, `cl.android` del merchant
