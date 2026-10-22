# Clase 7: Supervisión en Tiempo Real y Dashboards Administrativos en Millones de ₲ (FIUNA)

Suite pedagógica interactiva que materializa **8 laboratorios demostrativos** divididos en dos grandes bloques:
- **Parte I (Proyectos 1 al 4):** La frontera entre el **Tiempo Real Físico** (*Hard/Firm*, kHz, microsegundos) y el **Tiempo Real de Supervisión Operativa** (*Soft*, 60 fps, detección de jitter SSE e inercia mecánica).
- **Parte II (Proyectos 5 al 8):** **Dashboards Administrativos y Financieros en Millones de Guaraníes ($\text{₲}$)** que **NO requieren operaciones en tiempo real**, sino **cortes consistentes deterministas (SSR), simulaciones tarifarias/ROI e idempotencia transaccional** conectados 100% a **FastAPI**.

---

## 🚀 Cómo Ejecutar el Entorno Completo (2 Terminales)

> [!IMPORTANT]
> **Conexión 100% Estricta a FastAPI (`http://localhost:8007`):**
> Los Proyectos 2, 4, 5, 6, 7 y 8 obtienen y mutan el **100% de sus datos en el servidor FastAPI** (sin datos harcodeados de respaldo en el frontend). Debes tener corriendo FastAPI en el puerto `8007`.

### Terminal 1: Servidor Industrial y Financiero (FastAPI — Puerto 8007)

```bash
npm run backend
# O manualmente:
cd backend_fastapi && ~/.venv/bin/uvicorn main:app --reload --port 8007
```
- Documentación interactiva Swagger UI: `http://localhost:8007/docs`

### Terminal 2: Aplicación SvelteKit (Puerto 5173)

```bash
npm run dev
```
- Abre en el navegador: `http://localhost:5173`

---

## 🧭 Mapa de los 8 Laboratorios

### Parte I: Supervisión en Tiempo Real (Proyectos 1–4)
| Ruta | Proyecto | Endpoint FastAPI / Origen |
| :--- | :--- | :--- |
| `/proyecto-1-estres` | **1. El Banco de Estrés (kHz vs. 60 fps)** | Web Worker local (`100–1000 Hz`) |
| `/proyecto-2-jitter` | **2. El Semáforo de Latencia y Jitter** | `GET /api/jitter/stream` + `POST /api/jitter/config` |
| `/proyecto-3-eco` | **3. El Eco Visual (Consigna vs. Inercia)** | Modelo EDO 2do orden + Gauge SVG doble aguja |
| `/proyecto-4-scada` | **4. Dashboard SCADA Completo** | `GET /api/sensores`, `GET /api/scada/stream`, `POST /api/planta/paro-emergencia` |

### Parte II: Dashboards Administrativos en Millones de ₲ (Proyectos 5–8)
| Ruta | Proyecto | Endpoints FastAPI (`http://localhost:8007`) |
| :--- | :--- | :--- |
| `/admin-1-oee` | **5. OEE y Lucro Cesante por Turno (₲)** | `GET /api/admin/oee` + `POST /api/admin/oee/registrar-paro-auditado` |
| `/admin-2-energia-ande` | **6. Auditoría Energética Pliego ANDE (₲)** | `GET /api/admin/energia-ande` + `POST /api/admin/energia-ande/simular` |
| `/admin-3-capex-mantenimiento` | **7. Matriz CapEx/OpEx y Órdenes con Idempotencia (₲)** | `GET /api/admin/capex` + `POST /api/admin/capex/aprobar-orden` |
| `/admin-4-conciliacion-lotes` | **8. Conciliación de Lotes MES vs. ERP (₲)** | `GET /api/admin/conciliacion-lotes` + `POST /api/admin/conciliacion-lotes/dictamen` |
