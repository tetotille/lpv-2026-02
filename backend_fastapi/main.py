"""
Backend FastAPI para la Clase 7:
Tiempo Real Físico vs. Tiempo Real Administrativo
Cátedra: Lenguajes de Programación Visual (FIUNA) - Ingeniería Mecatrónica

Proporciona:
- PARTE I:
  - Simulación de planta industrial y adquisición de datos de sensores (ESP32, STM32).
  - Endpoint SSE con simulación de jitter de red, microcortes y cable desconectado (Proyecto 2).
  - Dashboard SCADA completo con SSE, calibración administrativa y paro de emergencia (Proyecto 4).
- PARTE II (Dashboards Administrativos en Millones de Guaraníes):
  - Proyecto 5: OEE y Lucro Cesante en Millones de ₲ (/api/admin/oee)
  - Proyecto 6: Auditoría Tarifaria ANDE Media Tensión (/api/admin/energia-ande)
  - Proyecto 7: Matriz CapEx/OpEx y Órdenes de Compra con Idempotencia (/api/admin/capex)
  - Proyecto 8: Conciliación Contable de Lotes MES vs. ERP (/api/admin/conciliacion-lotes)
"""

from contextlib import asynccontextmanager
from datetime import datetime
import asyncio
import hashlib
import json
import math
import random
import time
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

# ==============================================================================
# ESTADO EN MEMORIA DE LA PLANTA INDUSTRIAL (PARTE I)
# ==============================================================================

estado_planta: str = "EN_MARCHA"  # "EN_MARCHA" | "PARO_SOLICITADO"
modo_red_jitter: str = "nominal"  # "nominal" | "jitter_moderado" | "micro_cortes" | "cable_desconectado"

# 4 sensores industriales pre-cargados
sensores_db: Dict[str, Dict[str, Any]] = {
    "TI-101": {
        "id": "TI-101",
        "nodo": "ESP32-Caldera-01",
        "tipo": "Temperatura",
        "modelo": "DS18B20",
        "unidad": "°C",
        "min_nominal": 62.0,
        "max_nominal": 78.0,
        "rango_max": 85.0,
        "offset": 0.0,
        "frecuencia_muestreo_hz": 10,
        "valor_actual": 72.4,
        "_fisico": 72.4,
        "historial": []
    },
    "PI-102": {
        "id": "PI-102",
        "nodo": "ESP32-Caldera-01",
        "tipo": "Presión",
        "modelo": "BMP280",
        "unidad": "Bar",
        "min_nominal": 2.2,
        "max_nominal": 3.8,
        "rango_max": 5.0,
        "offset": 0.0,
        "frecuencia_muestreo_hz": 20,
        "valor_actual": 3.15,
        "_fisico": 3.15,
        "historial": []
    },
    "VI-201": {
        "id": "VI-201",
        "nodo": "STM32-Motor-A",
        "tipo": "Vibración",
        "modelo": "MPU6050",
        "unidad": "m/s²",
        "min_nominal": 2.0,
        "max_nominal": 4.5,
        "rango_max": 12.0,
        "offset": 0.0,
        "frecuencia_muestreo_hz": 100,
        "valor_actual": 3.40,
        "_fisico": 3.40,
        "historial": []
    },
    "HI-301": {
        "id": "HI-301",
        "nodo": "ESP32-Ambiente-02",
        "tipo": "Humedad",
        "modelo": "DHT22",
        "unidad": "%",
        "min_nominal": 50.0,
        "max_nominal": 68.0,
        "rango_max": 85.0,
        "offset": 0.0,
        "frecuencia_muestreo_hz": 5,
        "valor_actual": 58.5,
        "_fisico": 58.5,
        "historial": []
    }
}

# Inicializar historial de 30 lecturas para cada sensor
now_init_ms = int(time.time() * 1000)
for s_id, s in sensores_db.items():
    history = []
    base_val = s["valor_actual"]
    for i in range(30):
        t = now_init_ms - (30 - i) * 1000
        if s_id == "TI-101":
            v = round(base_val + random.uniform(-0.5, 0.5), 2)
        elif s_id == "PI-102":
            v = round(base_val + random.uniform(-0.06, 0.06), 2)
        elif s_id == "VI-201":
            v = round(base_val + random.uniform(-0.25, 0.25), 2)
        else:
            v = round(base_val + random.uniform(-0.6, 0.6), 2)
        v = max(0.0, min(s["rango_max"], v))
        history.append({"timestamp": t, "valor": v})
    s["historial"] = history
    s["_fisico"] = base_val
    s["valor_actual"] = history[-1]["valor"]

# Buffer circular de eventos de auditoría (máximo 100 eventos)
eventos_log: List[Dict[str, Any]] = []
_event_counter: int = 0


def registrar_evento(nivel: str, origen: str, mensaje: str) -> Dict[str, Any]:
    """Registra un evento en el log de auditoría del SCADA."""
    global _event_counter
    _event_counter += 1
    evento = {
        "id": _event_counter,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "nivel": nivel,  # "INFO" | "WARN" | "CRITICO"
        "origen": origen,
        "mensaje": mensaje
    }
    eventos_log.append(evento)
    if len(eventos_log) > 100:
        eventos_log.pop(0)
    return evento


# Registros iniciales
registrar_evento("INFO", "Sistema", "Servidor SCADA FastAPI inicializado en puerto 8007.")
registrar_evento("INFO", "Bus-CAN/Modbus", "Nodos remotos conectados: ESP32-Caldera-01, STM32-Motor-A, ESP32-Ambiente-02.")
registrar_evento("INFO", "Supervisor", "Modo de operación nominal establecido. Planta en marcha.")

# ==============================================================================
# MOTOR DE FÍSICA E INERCIA DE PLANTA (PARTE I)
# ==============================================================================

_ultimo_update_fisica: float = 0.0


def actualizar_sensores_fisica() -> None:
    """
    Avanza la simulación física de la planta mecatrónica:
    - En 'EN_MARCHA': oscilación nominal con inercia física de 1er/2do orden y ruido natural.
    - En 'PARO_SOLICITADO': decaimiento asintótico hacia condiciones de reposo/ambiente.
    - Aplica offset administrativo de calibración y satura a rango_max.
    """
    global _ultimo_update_fisica
    ahora_t = time.time()
    # Limitar frecuencia de actualización interna a ~200 ms mínimo
    if (ahora_t - _ultimo_update_fisica) < 0.20:
        return
    _ultimo_update_fisica = ahora_t
    ahora_ms = int(ahora_t * 1000)

    if estado_planta == "EN_MARCHA":
        # TI-101: Temperatura (Inercia térmica lenta de caldera)
        t_raw = sensores_db["TI-101"]["_fisico"]
        t_target = 72.0 + 1.8 * math.sin(ahora_t / 18.0)
        t_raw += (t_target - t_raw) * 0.08 + random.uniform(-0.12, 0.12)
        t_raw = max(20.0, min(85.0, t_raw))
        sensores_db["TI-101"]["_fisico"] = t_raw

        # PI-102: Presión de vapor (Dinámica intermedia)
        p_raw = sensores_db["PI-102"]["_fisico"]
        p_target = 3.20 + 0.22 * math.cos(ahora_t / 9.0)
        p_raw += (p_target - p_raw) * 0.12 + random.uniform(-0.03, 0.03)
        p_raw = max(0.0, min(5.0, p_raw))
        sensores_db["PI-102"]["_fisico"] = p_raw

        # VI-201: Vibración de motor (Dinámica rápida de rodamiento)
        v_raw = sensores_db["VI-201"]["_fisico"]
        v_target = 3.35 + 0.35 * math.sin(ahora_t / 3.5)
        v_raw += (v_target - v_raw) * 0.22 + random.uniform(-0.25, 0.25)
        v_raw = max(0.0, min(12.0, v_raw))
        sensores_db["VI-201"]["_fisico"] = v_raw

        # HI-301: Humedad ambiental de sala de calderas
        h_raw = sensores_db["HI-301"]["_fisico"]
        h_target = 58.0 + 1.8 * math.sin(ahora_t / 22.0)
        h_raw += (h_target - h_raw) * 0.05 + random.uniform(-0.20, 0.20)
        h_raw = max(10.0, min(85.0, h_raw))
        sensores_db["HI-301"]["_fisico"] = h_raw

    else:
        # PARO_SOLICITADO: Parada de actuadores y decaimiento a reposo físico
        # TI-101: Enfriamiento hacia ambiente (24.0 °C)
        t_raw = sensores_db["TI-101"]["_fisico"]
        t_raw += (24.0 - t_raw) * 0.025 + random.uniform(-0.04, 0.04)
        sensores_db["TI-101"]["_fisico"] = t_raw

        # PI-102: Despresurización hacia 0.0 Bar
        p_raw = sensores_db["PI-102"]["_fisico"]
        p_raw += (0.0 - p_raw) * 0.06 + random.uniform(-0.01, 0.01)
        p_raw = max(0.0, p_raw)
        sensores_db["PI-102"]["_fisico"] = p_raw

        # VI-201: Motor frenando hacia inmovilidad (0.02 m/s²)
        v_raw = sensores_db["VI-201"]["_fisico"]
        v_raw += (0.02 - v_raw) * 0.16 + random.uniform(-0.01, 0.01)
        v_raw = max(0.0, v_raw)
        sensores_db["VI-201"]["_fisico"] = v_raw

        # HI-301: Normalización a humedad ambiente (45.0 %)
        h_raw = sensores_db["HI-301"]["_fisico"]
        h_raw += (45.0 - h_raw) * 0.02 + random.uniform(-0.05, 0.05)
        sensores_db["HI-301"]["_fisico"] = h_raw

    # Calcular valor final aplicando offset de calibración y saturación
    for s in sensores_db.values():
        v_calibrado = round(s["_fisico"] + s["offset"], 2)
        v_calibrado = max(0.0, min(s["rango_max"], v_calibrado))
        s["valor_actual"] = v_calibrado
        s["historial"].append({"timestamp": ahora_ms, "valor": v_calibrado})
        if len(s["historial"]) > 100:
            s["historial"].pop(0)


async def physics_background_worker():
    """Tarea asíncrona en segundo plano que mantiene la planta activa a 4 Hz (250 ms)."""
    while True:
        try:
            actualizar_sensores_fisica()
            await asyncio.sleep(0.25)
        except asyncio.CancelledError:
            break
        except Exception:
            await asyncio.sleep(0.25)


# ==============================================================================
# CONFIGURACIÓN DE FASTAPI Y LIFESPAN
# ==============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicio: levantar tarea en segundo plano de simulación física
    bg_task = asyncio.create_task(physics_background_worker())
    yield
    # Apagado: cancelar tarea
    bg_task.cancel()
    try:
        await bg_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Planta Industrial FIUNA - Clase 7 SCADA API",
    description="Backend de telemetría y supervisión de tiempo real mecatrónico y dashboards administrativos en millones de Guaraníes (₲)",
    version="2.0.0",
    lifespan=lifespan
)

# Habilitar CORS para SvelteKit SSR y navegador
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================================================================
# ESQUEMAS PYDANTIC (PARTE I Y PARTE II)
# ==============================================================================

# --- PARTE I ---
class JitterConfigRequest(BaseModel):
    modo: str = Field(..., description="nominal | jitter_moderado | micro_cortes | cable_desconectado")


class CalibrarSensorRequest(BaseModel):
    offset: float = Field(..., description="Ajuste fino de compensación / offset")
    rango_max: float = Field(..., gt=0, description="Rango de fondo de escala del transductor")
    frecuencia_muestreo_hz: int = Field(..., gt=0, description="Tasa de adquisición en Hz")


class ParoEmergenciaRequest(BaseModel):
    accion: str = Field(..., description="'PARAR' o 'RESTAURAR'")
    motivo: Optional[str] = Field("Intervención manual desde consola SCADA", description="Motivo de la maniobra")
    operador: Optional[str] = Field("Operador SCADA FIUNA", description="Identificador del operador")


# --- PARTE II: PROYECTO 5 (OEE) ---
class RegistrarParoAuditadoRequest(BaseModel):
    linea: str = Field(..., description="L1, L2 o L3")
    turno: str = Field(..., description="Turno Mañana 06-14 | Turno Tarde 14-22 | Turno Noche 22-06")
    minutos: int = Field(..., gt=0, description="Duración de la parada en minutos")
    causa: str = Field(..., description="Motivo técnico o causa raíz del paro")
    responsable: str = Field(..., description="Ingeniero o técnico responsable de la auditoría")


# --- PARTE II: PROYECTO 6 (ANDE) ---
class SimularEnergiaAndeRequest(BaseModel):
    cos_phi_objetivo: float = Field(..., gt=0.5, le=1.0, description="Factor de potencia objetivo tras corrección capacitiva")
    pct_desplazamiento_punta: float = Field(..., ge=0.0, le=100.0, description="Porcentaje de carga a desplazar del horario punta a madrugada")
    inversion_capacitores_gs: int = Field(..., ge=0, description="Inversión proyectada en banco automático de capacitores en Guaraníes")


# --- PARTE II: PROYECTO 7 (CAPEX) ---
class AprobarOrdenCapexRequest(BaseModel):
    activo_id: str = Field(..., description="ID del activo crítico (ej. ACT-RED-01)")
    director_firmante: str = Field(..., description="Nombre del director que autoriza el desembolso")
    centro_costo: str = Field(..., description="Centro de costos asignado (ej. CC-MEC-401)")
    justificacion: str = Field(..., description="Fundamentación técnica del reemplazo")
    idempotency_key: str = Field(..., description="UUID o clave única de idempotencia financiera contra duplicados")


# --- PARTE II: PROYECTO 8 (CONCILIACIÓN LOTES) ---
class DictamenLoteRequest(BaseModel):
    lote_id: str = Field(..., description="ID del lote a dictaminar (ej. LOT-2026-804)")
    accion: str = Field(..., description="APROBADO_CONFORME | BLOQUEADO_RECALIBRACION")
    auditor: str = Field(..., description="Nombre del auditor o fiscal de aseguramiento")
    causa_raiz: str = Field(..., description="Causa técnica identificada del desvío de masa")
    observacion: str = Field(..., description="Comentarios adicionales para la pista de auditoría")


# ==============================================================================
# ENDPOINTS PARTE I: HEALTH CHECK, JITTER, SENSORES, PARO Y SCADA STREAM
# ==============================================================================

@app.get("/api/health", summary="Estado y salud del servidor SCADA")
async def health_check():
    """Retorna estado general de la planta, modo de red y sensores activos."""
    return {
        "status": "ok",
        "estado_planta": estado_planta,
        "modo_red_jitter": modo_red_jitter,
        "sensores_activos": len(sensores_db),
        "timestamp_servidor": int(time.time() * 1000)
    }


@app.get("/api/jitter/config", summary="Consultar modo de red y jitter actual")
async def get_jitter_config():
    """Retorna el perfil de red simulado actualmente."""
    return {
        "modo_red_jitter": modo_red_jitter
    }


@app.post("/api/jitter/config", summary="Configurar perfil de latencia/jitter")
async def set_jitter_config(payload: JitterConfigRequest):
    """
    Modifica el perfil de latencia de red:
    - nominal: ~100 ms constantes
    - jitter_moderado: 170 ms a 680 ms aleatorios
    - micro_cortes: ráfagas cortas alternadas con pausas de 950 ms a 1800 ms
    - cable_desconectado: omite paquetes de datos y envía sólo keepalives SSE
    """
    global modo_red_jitter
    modos_validos = ["nominal", "jitter_moderado", "micro_cortes", "cable_desconectado"]
    if payload.modo not in modos_validos:
        raise HTTPException(
            status_code=400,
            detail=f"Modo '{payload.modo}' no válido. Opciones: {modos_validos}"
        )

    modo_anterior = modo_red_jitter
    modo_red_jitter = payload.modo

    nivel = "WARN" if payload.modo in ["micro_cortes", "cable_desconectado"] else "INFO"
    registrar_evento(
        nivel=nivel,
        origen="JitterController",
        mensaje=f"Perfil de enlace de red modificado: '{modo_anterior}' -> '{modo_red_jitter}'"
    )

    return {
        "ok": True,
        "modo_red_jitter": modo_red_jitter,
        "mensaje": f"Modo de red actualizado a '{modo_red_jitter}'"
    }


@app.get("/api/jitter/stream", summary="Stream SSE con inyección de jitter y caídas")
async def jitter_stream(request: Request):
    """
    Emite telemetría de alta frecuencia vía Server-Sent Events (SSE).
    Permite demostrar la diferencia entre el determinismo físico y la latencia
    estadística TCP/IP, visualizando el fenómeno de 'dato congelado'.
    """
    async def event_generator():
        seq = 0
        t_anterior = time.time()
        try:
            while True:
                if await request.is_disconnected():
                    break

                # En modo cable desconectado: envía comentarios SSE sin evento data
                if modo_red_jitter == "cable_desconectado":
                    await asyncio.sleep(0.5)
                    # Comentario SSE: mantiene vivo el socket HTTP pero no dispara onmessage en la UI
                    yield ": cable_desconectado\n\n"
                    t_anterior = time.time()
                    continue

                # Determinar retardo según perfil de red configurado
                if modo_red_jitter == "nominal":
                    espera = 0.10
                elif modo_red_jitter == "jitter_moderado":
                    espera = random.uniform(0.18, 0.68)
                elif modo_red_jitter == "micro_cortes":
                    # 35% de probabilidad de microcorte severo (>900ms), 65% ráfaga rápida
                    if random.random() < 0.35:
                        espera = random.uniform(0.92, 1.85)
                    else:
                        espera = random.uniform(0.12, 0.25)
                else:
                    espera = 0.10

                await asyncio.sleep(espera)
                t_ahora = time.time()
                intervalo_ms = round((t_ahora - t_anterior) * 1000.0, 1)
                t_anterior = t_ahora
                seq += 1

                # Simulación de lectura física de transductor de nodo de pasarela
                valor_simulado = round(72.0 + random.normalvariate(0, 0.8), 2)

                payload = {
                    "seq": seq,
                    "timestamp_emision": int(t_ahora * 1000),
                    "valor": valor_simulado,
                    "unidad": "°C",
                    "nodo": "ESP32-Gateway-TX",
                    "modo_red": modo_red_jitter,
                    "intervalo_real_ms": intervalo_ms
                }
                yield f"data: {json.dumps(payload)}\n\n"
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.get("/api/sensores", summary="Listado completo de sensores y eventos recientes")
async def get_sensores():
    """
    Retorna el estado de la planta, todos los sensores industriales con
    sus metadatos y los últimos 25 eventos de auditoría para la consola SCADA.
    """
    sensores_lista = []
    for s in sensores_db.values():
        sensores_lista.append({
            "id": s["id"],
            "nodo": s["nodo"],
            "tipo": s["tipo"],
            "modelo": s["modelo"],
            "unidad": s["unidad"],
            "min_nominal": s["min_nominal"],
            "max_nominal": s["max_nominal"],
            "rango_max": s["rango_max"],
            "offset": s["offset"],
            "frecuencia_muestreo_hz": s["frecuencia_muestreo_hz"],
            "valor_actual": s["valor_actual"],
            "historial": s["historial"][-30:]
        })

    return {
        "estado_planta": estado_planta,
        "sensores": sensores_lista,
        "eventos_recientes": eventos_log[-25:]
    }


@app.get("/api/sensores/{sensor_id}", summary="Detalle individual, historial y estadísticas")
async def get_sensor_detalle(sensor_id: str):
    """
    Retorna la ficha técnica de un transductor con su historial completo
    y estadísticas descriptivas (mínimo, máximo, promedio, total_muestras).
    """
    if sensor_id not in sensores_db:
        raise HTTPException(status_code=404, detail="Transductor no encontrado")

    sensor = sensores_db[sensor_id]
    historial = sensor["historial"]
    valores = [h["valor"] for h in historial]

    minimo = round(min(valores), 2) if valores else 0.0
    maximo = round(max(valores), 2) if valores else 0.0
    promedio = round(sum(valores) / len(valores), 2) if valores else 0.0
    total_muestras = len(valores)

    sensor_info = {k: v for k, v in sensor.items() if not k.startswith("_")}

    return {
        "sensor": sensor_info,
        "historial": historial,
        "estadisticas": {
            "minimo": minimo,
            "maximo": maximo,
            "promedio": promedio,
            "total_muestras": total_muestras
        },
        "estado_planta": estado_planta
    }


@app.post("/api/sensores/{sensor_id}/calibrar", summary="Calibración administrativa del sensor")
async def calibrar_sensor(sensor_id: str, payload: CalibrarSensorRequest):
    """
    Aplica una consigna administrativa de calibración (offset, rango_max, frecuencia).
    Registra el cambio en la pista de auditoría industrial.
    """
    if sensor_id not in sensores_db:
        raise HTTPException(status_code=404, detail="Transductor no encontrado")

    sensor = sensores_db[sensor_id]
    sensor["offset"] = payload.offset
    sensor["rango_max"] = payload.rango_max
    sensor["frecuencia_muestreo_hz"] = payload.frecuencia_muestreo_hz

    # Recalcular valor actual con nuevo offset inmediatamente
    v_calibrado = round(sensor["_fisico"] + sensor["offset"], 2)
    sensor["valor_actual"] = max(0.0, min(sensor["rango_max"], v_calibrado))

    nivel = "WARN" if abs(payload.offset) > 2.0 else "INFO"
    registrar_evento(
        nivel=nivel,
        origen=f"SCADA-Calibración/{sensor_id}",
        mensaje=(
            f"Calibración administrativa aplicada a {sensor_id}: "
            f"offset={payload.offset:+0.2f}, rango_max={payload.rango_max}, "
            f"tasa={payload.frecuencia_muestreo_hz}Hz"
        )
    )

    sensor_ret = {k: v for k, v in sensor.items() if not k.startswith("_")}

    return {
        "ok": True,
        "mensaje": f"Sensor {sensor_id} calibrado exitosamente con offset {payload.offset:+0.2f}",
        "sensor": sensor_ret
    }


@app.post("/api/planta/paro-emergencia", summary="Paro de emergencia administrativo vs. Físico")
async def paro_emergencia(payload: ParoEmergenciaRequest):
    """
    Ejecuta una solicitud de paro o restauración por software.
    Destaca el contraste entre la latencia administrativa de una petición HTTP
    y el determinismo de un relé físico de seguridad Categoría 4 / SIL 3.
    """
    global estado_planta
    t0 = time.perf_counter()

    if payload.accion == "PARAR":
        estado_planta = "PARO_SOLICITADO"
        dt_ms = (time.perf_counter() - t0) * 1000.0

        registrar_evento(
            nivel="CRITICO",
            origen=f"Operador/{payload.operador}",
            mensaje=(
                f"PARO DE EMERGENCIA SOLICITADO. Motivo: {payload.motivo}. "
                f"Tiempo de procesamiento HTTP administrativo: {dt_ms:.3f} ms."
            )
        )

        return {
            "ok": True,
            "estado_planta": estado_planta,
            "mensaje": "Paro de emergencia administrativo procesado. Actuadores pasando a modo reposo.",
            "advertencia_seguridad": (
                "Solicitud administrativa procesada por software "
                "(NO sustituye a un relé físico cableado Categoría 4 / SIL 3)."
            )
        }

    elif payload.accion == "RESTAURAR":
        estado_planta = "EN_MARCHA"
        registrar_evento(
            nivel="INFO",
            origen=f"Operador/{payload.operador}",
            mensaje=f"Planta restaurada a EN_MARCHA. Motivo: {payload.motivo}."
        )

        return {
            "ok": True,
            "estado_planta": estado_planta,
            "mensaje": "Planta restaurada a operación nominal EN_MARCHA.",
            "advertencia_seguridad": (
                "Solicitud administrativa procesada por software "
                "(NO sustituye a un relé físico cableado Categoría 4 / SIL 3)."
            )
        }
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Acción '{payload.accion}' no válida. Use 'PARAR' o 'RESTAURAR'."
        )


@app.get("/api/scada/stream", summary="Stream SSE de telemetría continua SCADA a 250 ms")
async def scada_stream(request: Request):
    """
    Emite a 4 Hz (cada 250 ms) el estado integral de la planta, las lecturas
    actualizadas con inercia física de los 4 sensores y el último evento de auditoría.
    """
    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break

                await asyncio.sleep(0.25)
                actualizar_sensores_fisica()

                sensores_payload = []
                for s in sensores_db.values():
                    sensores_payload.append({
                        "id": s["id"],
                        "nodo": s["nodo"],
                        "tipo": s["tipo"],
                        "modelo": s["modelo"],
                        "unidad": s["unidad"],
                        "min_nominal": s["min_nominal"],
                        "max_nominal": s["max_nominal"],
                        "rango_max": s["rango_max"],
                        "offset": s["offset"],
                        "frecuencia_muestreo_hz": s["frecuencia_muestreo_hz"],
                        "valor_actual": s["valor_actual"],
                        "historial": s["historial"][-30:]
                    })

                payload = {
                    "timestamp": int(time.time() * 1000),
                    "estado_planta": estado_planta,
                    "sensores": sensores_payload,
                    "ultimo_evento": eventos_log[-1] if eventos_log else None
                }
                yield f"data: {json.dumps(payload)}\n\n"
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# ==============================================================================
# PARTE II - PROYECTO 5: OEE Y LUCRO CESANTE EN MILLONES DE GUARANÍES (₲)
# ==============================================================================

LINEAS_CATALOGO = [
    {
        "id": "L1",
        "nombre": "L1: Embotellado PET Alta Velocidad",
        "costo_minuto_parada_gs": 1450000,
        "velocidad_nominal_u_h": 18000
    },
    {
        "id": "L2",
        "nombre": "L2: Envasado Aséptico Tetra",
        "costo_minuto_parada_gs": 1850000,
        "velocidad_nominal_u_h": 12000
    },
    {
        "id": "L3",
        "nombre": "L3: Empaque y Paletizado Robótico",
        "costo_minuto_parada_gs": 980000,
        "velocidad_nominal_u_h": 24000
    }
]

COSTOS_MINUTO_DICT = {l["id"]: l["costo_minuto_parada_gs"] for l in LINEAS_CATALOGO}

# Incidentes de paradas registrados en memoria
paros_auditados_db: List[Dict[str, Any]] = [
    {
        "id": "PARO-891",
        "fecha_hora": "2026-10-21 15:40",
        "linea": "L1",
        "turno": "Turno Tarde 14-22",
        "minutos": 45,
        "causa": "Atasco en túnel de retracción y falla de fotocélula",
        "costo_calculado_gs": 65250000,
        "responsable": "Ing. Carlos Benítez"
    },
    {
        "id": "PARO-890",
        "fecha_hora": "2026-10-20 23:15",
        "linea": "L2",
        "turno": "Turno Noche 22-06",
        "minutos": 60,
        "causa": "Microfisura en válvula de vapor aséptico",
        "costo_calculado_gs": 111000000,
        "responsable": "Tec. Marcos Duarte"
    },
    {
        "id": "PARO-889",
        "fecha_hora": "2026-10-19 10:20",
        "linea": "L3",
        "turno": "Turno Mañana 06-14",
        "minutos": 30,
        "causa": "Calibración de pinza neumática del robot KUKA",
        "costo_calculado_gs": 29400000,
        "responsable": "Ing. Andrea Ruiz"
    },
    {
        "id": "PARO-888",
        "fecha_hora": "2026-10-18 18:05",
        "linea": "L1",
        "turno": "Turno Tarde 14-22",
        "minutos": 25,
        "causa": "Falla de sincronismo en servocinta de ingreso",
        "costo_calculado_gs": 36250000,
        "responsable": "Tec. Ramón Galeano"
    },
    {
        "id": "PARO-887",
        "fecha_hora": "2026-10-17 04:10",
        "linea": "L2",
        "turno": "Turno Noche 22-06",
        "minutos": 50,
        "causa": "Lavado CIP extraordinario por desvío de conductividad",
        "costo_calculado_gs": 92500000,
        "responsable": "Ing. Carlos Benítez"
    }
]

SERIE_DIARIA_BASE_OEE = [
    {"dia_num": 1, "fecha": "08/10", "oee_pct": 74.2, "perdida_millones_gs": 38.5, "disponibilidad_pct": 77.0},
    {"dia_num": 2, "fecha": "09/10", "oee_pct": 76.5, "perdida_millones_gs": 32.1, "disponibilidad_pct": 79.2},
    {"dia_num": 3, "fecha": "10/10", "oee_pct": 71.8, "perdida_millones_gs": 44.2, "disponibilidad_pct": 75.1},
    {"dia_num": 4, "fecha": "11/10", "oee_pct": 78.4, "perdida_millones_gs": 29.0, "disponibilidad_pct": 81.3},
    {"dia_num": 5, "fecha": "12/10", "oee_pct": 79.6, "perdida_millones_gs": 26.4, "disponibilidad_pct": 82.5},
    {"dia_num": 6, "fecha": "13/10", "oee_pct": 68.2, "perdida_millones_gs": 58.0, "disponibilidad_pct": 70.4},
    {"dia_num": 7, "fecha": "14/10", "oee_pct": 77.1, "perdida_millones_gs": 31.8, "disponibilidad_pct": 80.0},
    {"dia_num": 8, "fecha": "15/10", "oee_pct": 80.5, "perdida_millones_gs": 24.5, "disponibilidad_pct": 83.2},
    {"dia_num": 9, "fecha": "16/10", "oee_pct": 75.3, "perdida_millones_gs": 35.6, "disponibilidad_pct": 78.4},
    {"dia_num": 10, "fecha": "17/10", "oee_pct": 72.0, "perdida_millones_gs": 48.2, "disponibilidad_pct": 74.8},
    {"dia_num": 11, "fecha": "18/10", "oee_pct": 78.9, "perdida_millones_gs": 28.3, "disponibilidad_pct": 81.6},
    {"dia_num": 12, "fecha": "19/10", "oee_pct": 81.4, "perdida_millones_gs": 22.0, "disponibilidad_pct": 84.5},
    {"dia_num": 13, "fecha": "20/10", "oee_pct": 70.1, "perdida_millones_gs": 52.8, "disponibilidad_pct": 72.9},
    {"dia_num": 14, "fecha": "21/10", "oee_pct": 79.1, "perdida_millones_gs": 26.8, "disponibilidad_pct": 82.4}
]


@app.get("/api/admin/oee", summary="Dashboard OEE, disponibilidad y lucro cesante industrial")
async def get_admin_oee(
    linea: str = Query("TODAS", description="TODAS | L1 | L2 | L3"),
    periodo: str = Query("mes", description="7d | mes | trimestre"),
    meta_disponibilidad: float = Query(85.0, description="Meta ejecutiva de disponibilidad porcentual")
):
    """
    Retorna métricas consolidadas de OEE industrial y lucro cesante financiero en ₲.
    Ajusta dinámicamente según la línea seleccionada, período y meta corporativa.
    """
    lineas_validas = ["TODAS", "L1", "L2", "L3"]
    if linea not in lineas_validas:
        raise HTTPException(status_code=400, detail=f"Línea '{linea}' no válida. Opciones: {lineas_validas}")

    periodos_validos = ["7d", "mes", "trimestre"]
    if periodo not in periodos_validos:
        raise HTTPException(status_code=400, detail=f"Período '{periodo}' no válido. Opciones: {periodos_validos}")

    # Filtrar paros según línea
    paros_filtrados = [p for p in paros_auditados_db if (linea == "TODAS" or p["linea"] == linea)]

    # Costo por minuto promedio de la línea o planta
    if linea in COSTOS_MINUTO_DICT:
        costo_minuto_promedio_gs = COSTOS_MINUTO_DICT[linea]
    else:
        costo_minuto_promedio_gs = round(sum(COSTOS_MINUTO_DICT.values()) / len(COSTOS_MINUTO_DICT))

    # Base de cálculo de OEE según línea
    if linea == "L1":
        disp_base, rend_base, cal_base = 81.2, 89.0, 98.2
    elif linea == "L2":
        disp_base, rend_base, cal_base = 74.5, 86.2, 96.5
    elif linea == "L3":
        disp_base, rend_base, cal_base = 84.1, 91.0, 98.6
    else:
        disp_base, rend_base, cal_base = 79.9, 88.5, 97.8

    # Modificador según período
    mult_periodo = 1.02 if periodo == "7d" else (0.98 if periodo == "trimestre" else 1.0)
    disponibilidad_pct = round(min(99.0, disp_base * mult_periodo), 1)
    rendimiento_pct = round(min(99.0, rend_base * mult_periodo), 1)
    calidad_pct = round(min(99.5, cal_base * mult_periodo), 1)
    oee_pct = round((disponibilidad_pct * rendimiento_pct * calidad_pct) / 10000.0, 1)

    # Pérdidas financieras acumuladas
    minutos_parada_total = sum(p["minutos"] for p in paros_filtrados)
    perdida_paradas_gs = sum(p["costo_calculado_gs"] for p in paros_filtrados)
    perdida_rendimiento_gs = round(perdida_paradas_gs * 0.42)
    perdida_calidad_gs = round(perdida_paradas_gs * 0.20)
    lucro_cesante_total_gs = perdida_paradas_gs + perdida_rendimiento_gs + perdida_calidad_gs

    # Ahorro potencial si se alcanza la meta de disponibilidad
    if meta_disponibilidad > disponibilidad_pct:
        gap = meta_disponibilidad - disponibilidad_pct
        ahorro_potencial_meta_gs = round((lucro_cesante_total_gs / max(1.0, 100.0 - disponibilidad_pct)) * gap)
    else:
        ahorro_potencial_meta_gs = 0

    # Turnos de operación
    minutos_manana = sum(p["minutos"] for p in paros_filtrados if "Mañana" in p["turno"])
    minutos_tarde = sum(p["minutos"] for p in paros_filtrados if "Tarde" in p["turno"])
    minutos_noche = sum(p["minutos"] for p in paros_filtrados if "Noche" in p["turno"])

    turnos = [
        {
            "turno": "Turno Mañana 06-14",
            "oee_pct": round(min(99.0, oee_pct + 3.2), 1),
            "disponibilidad_pct": round(min(99.0, disponibilidad_pct + 3.8), 1),
            "minutos_paro": minutos_manana if minutos_manana > 0 else 75,
            "lucro_cesante_gs": sum(p["costo_calculado_gs"] for p in paros_filtrados if "Mañana" in p["turno"]) or round(lucro_cesante_total_gs * 0.22),
            "causa_principal": "Ajuste de guías mecánicas y cambios de formato"
        },
        {
            "turno": "Turno Tarde 14-22",
            "oee_pct": round(max(50.0, oee_pct - 1.5), 1),
            "disponibilidad_pct": round(max(50.0, disponibilidad_pct - 1.8), 1),
            "minutos_paro": minutos_tarde if minutos_tarde > 0 else 125,
            "lucro_cesante_gs": sum(p["costo_calculado_gs"] for p in paros_filtrados if "Tarde" in p["turno"]) or round(lucro_cesante_total_gs * 0.35),
            "causa_principal": "Atascos en túnel y fotocélulas sucias"
        },
        {
            "turno": "Turno Noche 22-06",
            "oee_pct": round(max(40.0, oee_pct - 5.8), 1),
            "disponibilidad_pct": round(max(45.0, disponibilidad_pct - 6.2), 1),
            "minutos_paro": minutos_noche if minutos_noche > 0 else 190,
            "lucro_cesante_gs": sum(p["costo_calculado_gs"] for p in paros_filtrados if "Noche" in p["turno"]) or round(lucro_cesante_total_gs * 0.43),
            "causa_principal": "Válvulas asépticas y demoras en limpieza CIP"
        }
    ]

    return {
        "linea_seleccionada": linea,
        "periodo_seleccionado": periodo,
        "meta_disponibilidad": meta_disponibilidad,
        "lineas_catalogo": LINEAS_CATALOGO,
        "kpis": {
            "oee_pct": oee_pct,
            "disponibilidad_pct": disponibilidad_pct,
            "rendimiento_pct": rendimiento_pct,
            "calidad_pct": calidad_pct,
            "minutos_parada_total": minutos_parada_total,
            "costo_minuto_promedio_gs": costo_minuto_promedio_gs,
            "lucro_cesante_total_gs": lucro_cesante_total_gs,
            "perdida_paradas_gs": perdida_paradas_gs,
            "perdida_rendimiento_gs": perdida_rendimiento_gs,
            "perdida_calidad_gs": perdida_calidad_gs,
            "ahorro_potencial_meta_gs": ahorro_potencial_meta_gs
        },
        "turnos": turnos,
        "serie_diaria": SERIE_DIARIA_BASE_OEE,
        "paros_registrados": paros_filtrados
    }


@app.post("/api/admin/oee/registrar-paro-auditado", summary="Registrar incidente de paro de línea auditado")
async def registrar_paro_auditado(payload: RegistrarParoAuditadoRequest):
    """
    Registra un paro técnico auditado en memoria, calcula su impacto monetario en Guaraníes
    según la tarifa de parada de la línea y actualiza el lucro cesante total acumulado.
    """
    costo_min = COSTOS_MINUTO_DICT.get(payload.linea, 1426667)
    costo_calculado_gs = payload.minutos * costo_min

    nuevo_id = f"PARO-{len(paros_auditados_db) + 892}"
    nuevo_paro = {
        "id": nuevo_id,
        "fecha_hora": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "linea": payload.linea,
        "turno": payload.turno,
        "minutos": payload.minutos,
        "causa": payload.causa,
        "costo_calculado_gs": costo_calculado_gs,
        "responsable": payload.responsable
    }
    paros_auditados_db.insert(0, nuevo_paro)

    # Auditoría SCADA
    registrar_evento(
        nivel="CRITICO" if payload.minutos >= 30 else "WARN",
        origen=f"AuditoríaOEE/{payload.linea}",
        mensaje=f"Paro auditado de {payload.minutos} min en {payload.linea} ({payload.turno}). Causa: {payload.causa}. Lucro cesante: ₲ {costo_calculado_gs:,.0f}".replace(",", ".")
    )

    nuevo_lucro_cesante_total_gs = sum(p["costo_calculado_gs"] for p in paros_auditados_db)

    return {
        "ok": True,
        "mensaje": f"Paro auditado de {payload.minutos} min en {payload.linea} registrado con lucro cesante de ₲ {costo_calculado_gs:,.0f}.".replace(",", "."),
        "paro_registrado": nuevo_paro,
        "nuevo_lucro_cesante_total_gs": nuevo_lucro_cesante_total_gs
    }


# ==============================================================================
# PARTE II - PROYECTO 6: AUDITORÍA TARIFARIA ANDE MEDIA TENSIÓN
# ==============================================================================

PLIEGO_ANDE = {
    "categoria": "Industrial Media Tensión (23 kV) - Pliego Tarifario ANDE",
    "tarifa_punta_gs_kwh": 685,
    "tarifa_fuera_punta_gs_kwh": 310,
    "cargo_potencia_punta_gs_kw": 41500,
    "cos_phi_umbral_ande": 0.92,
    "penalizacion_pct_por_centesimo": 4.0
}

# Perfil base de demanda horaria en kW (24 horas)
CURVA_BASE_ANDE_KW = [
    285.0, 275.0, 270.0, 272.0, 280.0, 310.0,  # 00:00 - 05:00
    420.0, 465.0, 485.0, 490.0, 480.0, 475.0,  # 06:00 - 11:00
    440.0, 460.0, 475.0, 480.0, 490.0, 495.0,  # 12:00 - 17:00
    515.0, 530.0, 525.0, 510.0, 350.0, 310.0   # 18:00 - 23:00 (18..21 punta)
]

# Parámetros activos de simulación energética en memoria
simulacion_ande_activa: Dict[str, Any] = {
    "cos_phi_objetivo": 0.96,
    "pct_desplazamiento_punta": 35.0,
    "inversion_capacitores_gs": 95000000
}


def calcular_auditoria_ande(cos_phi_obj: float, pct_desp: float, inv_capacitores: int) -> Dict[str, Any]:
    """Calcula la auditoría tarifaria y curva 24h optimizada con el pliego ANDE."""
    # Situación actual mensual
    consumo_punta = 58400
    consumo_fuera_punta = 215600
    demanda_maxima_punta = 520.0
    cos_phi_actual = 0.81
    recargo_reactiva_pct = 44.0  # (0.92 - 0.81) * 100 * 4%

    costo_energia_base_actual = (consumo_punta * 685) + (consumo_fuera_punta * 310)  # 106.840.000 ₲
    costo_potencia_actual = int(demanda_maxima_punta * 41500)  # 21.580.000 ₲
    multa_reactiva_actual = int(costo_energia_base_actual * (recargo_reactiva_pct / 100.0))  # 47.009.600 ₲
    factura_total_actual = costo_energia_base_actual + costo_potencia_actual + multa_reactiva_actual  # 175.429.600 ₲

    situacion_actual = {
        "consumo_mensual_punta_kwh": consumo_punta,
        "consumo_mensual_fuera_punta_kwh": consumo_fuera_punta,
        "demanda_maxima_punta_kw": demanda_maxima_punta,
        "cos_phi_actual": cos_phi_actual,
        "recargo_reactiva_pct": recargo_reactiva_pct,
        "costo_energia_base_gs": costo_energia_base_actual,
        "costo_potencia_gs": costo_potencia_actual,
        "multa_reactiva_gs": multa_reactiva_actual,
        "factura_total_mensual_gs": factura_total_actual
    }

    # Desplazamiento de punta a madrugada (01:00 a 05:00)
    ratio_desp = pct_desp / 100.0
    kwh_desplazados = round(consumo_punta * ratio_desp)
    nuevo_punta = consumo_punta - kwh_desplazados
    nuevo_fuera_punta = consumo_fuera_punta + kwh_desplazados
    nuevo_costo_energia_base = (nuevo_punta * 685) + (nuevo_fuera_punta * 310)

    # Demanda punta mitigada por aplanamiento de curva de carga
    demanda_optimizada_kw = round(demanda_maxima_punta * (1.0 - ratio_desp * 0.28), 1)
    nuevo_costo_potencia = int(demanda_optimizada_kw * 41500)

    # Multa reactiva recalculada según cos_phi_objetivo
    if cos_phi_obj < 0.92:
        deficit_centesimos = round((0.92 - cos_phi_obj) * 100.0, 1)
        nueva_multa_pct = deficit_centesimos * 4.0
        nueva_multa_reactiva_gs = int(nuevo_costo_energia_base * (nueva_multa_pct / 100.0))
    else:
        nueva_multa_reactiva_gs = 0

    nueva_factura_mensual = nuevo_costo_energia_base + nuevo_costo_potencia + nueva_multa_reactiva_gs
    ahorro_mensual_gs = factura_total_actual - nueva_factura_mensual
    ahorro_anual_gs = ahorro_mensual_gs * 12
    payback_meses = round(inv_capacitores / ahorro_mensual_gs, 1) if ahorro_mensual_gs > 0 else 999.0
    roi_anual_pct = round(((ahorro_anual_gs - inv_capacitores) / inv_capacitores) * 100.0, 1) if inv_capacitores > 0 else 0.0

    ultima_simulacion = {
        "cos_phi_objetivo": cos_phi_obj,
        "pct_desplazamiento_punta": pct_desp,
        "inversion_capacitores_gs": inv_capacitores,
        "nueva_factura_mensual_gs": nueva_factura_mensual,
        "nueva_multa_reactiva_gs": nueva_multa_reactiva_gs,
        "ahorro_mensual_gs": ahorro_mensual_gs,
        "ahorro_anual_gs": ahorro_anual_gs,
        "payback_meses": payback_meses,
        "roi_anual_pct": roi_anual_pct
    }

    # Curva horaria 24 horas
    curva_horaria = []
    kw_reducido_punta_total = sum(CURVA_BASE_ANDE_KW[h] * ratio_desp for h in [18, 19, 20, 21])
    kw_adicional_madrugada = kw_reducido_punta_total / 5.0  # redistribuido en 01:00 a 05:00

    for h in range(24):
        es_punta = (18 <= h < 22)
        kw_act = CURVA_BASE_ANDE_KW[h]
        if es_punta:
            kw_opt = round(kw_act * (1.0 - ratio_desp), 1)
        elif 1 <= h <= 5:
            kw_opt = round(kw_act + kw_adicional_madrugada, 1)
        else:
            kw_opt = kw_act

        tarifa = 685 if es_punta else 310
        costo_act = int(kw_act * tarifa)
        costo_opt = int(kw_opt * tarifa)

        curva_horaria.append({
            "hora": h,
            "etiqueta": f"{h:02d}:00",
            "es_horario_punta": es_punta,
            "kw_actual": kw_act,
            "kw_optimizado": kw_opt,
            "costo_hora_actual_gs": costo_act,
            "costo_hora_optimizado_gs": costo_opt
        })

    return {
        "pliego_ande": PLIEGO_ANDE,
        "situacion_actual": situacion_actual,
        "ultima_simulacion": ultima_simulacion,
        "curva_horaria_24h": curva_horaria
    }


@app.get("/api/admin/energia-ande", summary="Auditoría energética y facturación ANDE Media Tensión")
async def get_energia_ande():
    """Retorna el pliego ANDE, factura actual, simulación activa y curva de carga 24h."""
    return calcular_auditoria_ande(
        cos_phi_obj=simulacion_ande_activa["cos_phi_objetivo"],
        pct_desp=simulacion_ande_activa["pct_desplazamiento_punta"],
        inv_capacitores=simulacion_ande_activa["inversion_capacitores_gs"]
    )


@app.post("/api/admin/energia-ande/simular", summary="Simular optimización tarifaria ANDE y desplazamiento de punta")
async def simular_energia_ande(payload: SimularEnergiaAndeRequest):
    """
    Recalcula la auditoría tarifaria reduciendo la demanda en horario de punta (18:00-22:00),
    redistribuyendo carga en madrugada a tarifa reducida y corrigiendo factor de potencia.
    """
    global simulacion_ande_activa
    simulacion_ande_activa["cos_phi_objetivo"] = payload.cos_phi_objetivo
    simulacion_ande_activa["pct_desplazamiento_punta"] = payload.pct_desplazamiento_punta
    simulacion_ande_activa["inversion_capacitores_gs"] = payload.inversion_capacitores_gs

    resultado = calcular_auditoria_ande(
        cos_phi_obj=payload.cos_phi_objetivo,
        pct_desp=payload.pct_desplazamiento_punta,
        inv_capacitores=payload.inversion_capacitores_gs
    )

    registrar_evento(
        nivel="INFO",
        origen="AuditoríaANDE/Simulador",
        mensaje=(
            f"Simulación ANDE ejecutada: cos(φ)={payload.cos_phi_objetivo}, "
            f"desplazamiento={payload.pct_desplazamiento_punta}%. "
            f"Ahorro anual estimado: ₲ {resultado['ultima_simulacion']['ahorro_anual_gs']:,.0f}"
        ).replace(",", ".")
    )

    return resultado


# ==============================================================================
# PARTE II - PROYECTO 7: MATRIZ CAPEX/OPEX Y ÓRDENES DE COMPRA CON IDEMPOTENCIA
# ==============================================================================

presupuesto_capex_db: Dict[str, int] = {
    "presupuesto_anual_gs": 1200000000,
    "comprometido_gs": 0,
    "disponible_gs": 1200000000
}


def generar_curva_weibull(costo_preventivo: int, costo_falla: int, prob_mes1: float) -> List[Dict[str, Any]]:
    """Genera curva de degradación y riesgo acumulado Weibull a 12 meses."""
    p1 = max(0.05, min(0.95, prob_mes1 / 100.0))
    beta = 1.75  # Desgaste mecánico acelerado típico de fatiga en rodamientos y engranajes
    eta = 1.0 / ((-math.log(1.0 - p1)) ** (1.0 / beta))

    curva = []
    costo_prev_millones = round(costo_preventivo / 1000000.0, 1)
    for mes in range(1, 13):
        prob_acum = 1.0 - math.exp(- ((mes / eta) ** beta))
        prob_acum_pct = round(min(99.9, prob_acum * 100.0), 1)
        riesgo_esperado_millones = round((costo_falla * (prob_acum_pct / 100.0)) / 1000000.0, 2)
        curva.append({
            "mes": mes,
            "costo_preventivo_millones": costo_prev_millones,
            "costo_riesgo_esperado_millones": riesgo_esperado_millones,
            "prob_acumulada_pct": prob_acum_pct
        })
    return curva


activos_capex_db: List[Dict[str, Any]] = [
    {
        "id": "ACT-RED-01",
        "nombre": "Reductor Planetario Horno Rotativo",
        "linea": "Línea 1",
        "rul_dias_estimados": 14,
        "prob_falla_30d_pct": 68.5,
        "costo_preventivo_capex_gs": 142000000,
        "costo_falla_catastrofica_gs": 685000000,
        "riesgo_ponderado_gs": round(685000000 * 0.685),
        "estado_orden": "PENDIENTE_DECISION",
        "curva_weibull_12m": generar_curva_weibull(142000000, 685000000, 68.5)
    },
    {
        "id": "ACT-COMP-02",
        "nombre": "Compresor de Tornillo Atlas 160 kW",
        "linea": "Planta Neumática",
        "rul_dias_estimados": 22,
        "prob_falla_30d_pct": 54.0,
        "costo_preventivo_capex_gs": 98500000,
        "costo_falla_catastrofica_gs": 420000000,
        "riesgo_ponderado_gs": round(420000000 * 0.54),
        "estado_orden": "PENDIENTE_DECISION",
        "curva_weibull_12m": generar_curva_weibull(98500000, 420000000, 54.0)
    },
    {
        "id": "ACT-BOMB-03",
        "nombre": "Bomba Multietapa de Alimentación Caldera",
        "linea": "Sala de Vapor",
        "rul_dias_estimados": 45,
        "prob_falla_30d_pct": 31.0,
        "costo_preventivo_capex_gs": 64000000,
        "costo_falla_catastrofica_gs": 290000000,
        "riesgo_ponderado_gs": round(290000000 * 0.31),
        "estado_orden": "PENDIENTE_DECISION",
        "curva_weibull_12m": generar_curva_weibull(64000000, 290000000, 31.0)
    },
    {
        "id": "ACT-SERV-04",
        "nombre": "Servomotor y Husillo Empacadora Robótica",
        "linea": "Línea 3",
        "rul_dias_estimados": 60,
        "prob_falla_30d_pct": 19.5,
        "costo_preventivo_capex_gs": 52000000,
        "costo_falla_catastrofica_gs": 195000000,
        "riesgo_ponderado_gs": round(195000000 * 0.195),
        "estado_orden": "PENDIENTE_DECISION",
        "curva_weibull_12m": generar_curva_weibull(52000000, 195000000, 19.5)
    }
]

ordenes_capex_db: List[Dict[str, Any]] = []


@app.get("/api/admin/capex", summary="Matriz CapEx/OpEx, activos críticos y órdenes emitidas")
async def get_admin_capex():
    """Retorna el balance presupuestario, los 4 activos con análisis Weibull y las órdenes aprobadas."""
    return {
        "presupuesto": presupuesto_capex_db,
        "activos": activos_capex_db,
        "ordenes_aprobadas": ordenes_capex_db
    }


@app.post("/api/admin/capex/aprobar-orden", summary="Emitir orden de compra CapEx con protección de idempotencia")
async def aprobar_orden_capex(payload: AprobarOrdenCapexRequest):
    """
    Emite una orden de compra CapEx para reemplazo proactivo del activo.
    Implementa protección de idempotencia financiera estricta: rechaza solicitudes repetidas con HTTP 409.
    """
    # 1. Verificación de Idempotencia estricta
    for ord_existente in ordenes_capex_db:
        if ord_existente.get("idempotency_key") == payload.idempotency_key:
            raise HTTPException(
                status_code=409,
                detail=f"Rechazo por Idempotencia Financiera: La clave '{payload.idempotency_key}' ya fue ejecutada previamente. Se evitó duplicar un desembolso millonario."
            )

    # 2. Localizar activo
    activo = next((a for a in activos_capex_db if a["id"] == payload.activo_id), None)
    if not activo:
        raise HTTPException(status_code=404, detail=f"Activo '{payload.activo_id}' no encontrado.")

    monto = activo["costo_preventivo_capex_gs"]
    if presupuesto_capex_db["disponible_gs"] < monto:
        raise HTTPException(
            status_code=400,
            detail=f"Fondos insuficientes: Disponible ₲ {presupuesto_capex_db['disponible_gs']:,} < Requerido ₲ {monto:,}".replace(",", ".")
        )

    # 3. Descontar del presupuesto disponible
    presupuesto_capex_db["comprometido_gs"] += monto
    presupuesto_capex_db["disponible_gs"] = presupuesto_capex_db["presupuesto_anual_gs"] - presupuesto_capex_db["comprometido_gs"]

    # 4. Actualizar estado del activo y mitigar riesgo
    activo["estado_orden"] = "ORDEN_EMITIDA"
    activo["prob_falla_30d_pct"] = 2.5
    activo["riesgo_ponderado_gs"] = round(activo["costo_falla_catastrofica_gs"] * 0.025)

    # 5. Generar orden con hash criptográfico de auditoría
    orden_num = len(ordenes_capex_db) + 1
    orden_id = f"ORD-2026-{orden_num:03d}"
    ahorro_riesgo_evitado = activo["costo_falla_catastrofica_gs"] - monto

    raw_hash = f"{orden_id}:{payload.idempotency_key}:{monto}:{payload.director_firmante}"
    hash_auditoria = hashlib.sha256(raw_hash.encode()).hexdigest()[:16].upper()

    nueva_orden = {
        "orden_id": orden_id,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "activo_id": activo["id"],
        "nombre_activo": activo["nombre"],
        "monto_aprobado_gs": monto,
        "ahorro_riesgo_evitado_gs": ahorro_riesgo_evitado,
        "director_firmante": payload.director_firmante,
        "centro_costo": payload.centro_costo,
        "justificacion": payload.justificacion,
        "idempotency_key": payload.idempotency_key,
        "hash_auditoria": f"SHA256-{hash_auditoria}"
    }
    ordenes_capex_db.insert(0, nueva_orden)

    # 6. Registrar en auditoría SCADA
    registrar_evento(
        nivel="INFO",
        origen=f"CapEx/{payload.centro_costo}",
        mensaje=f"Orden {orden_id} aprobada por {payload.director_firmante} para {activo['nombre']} (₲ {monto:,.0f}). Hash: {hash_auditoria}".replace(",", ".")
    )

    return {
        "ok": True,
        "mensaje": f"Orden de compra {orden_id} emitida exitosamente para {activo['nombre']}.",
        "orden": nueva_orden,
        "presupuesto": presupuesto_capex_db
    }


# ==============================================================================
# PARTE II - PROYECTO 8: CONCILIACIÓN CONTABLE DE LOTES MES VS. ERP
# ==============================================================================

lotes_conciliacion_db: List[Dict[str, Any]] = [
    {
        "lote_id": "LOT-2026-801",
        "producto": "Néctar de Durazno 1L Tetra",
        "fecha_cierre": "2026-10-15 08:30",
        "masa_erp_almacen_kg": 25000.0,
        "masa_mes_caudalimetro_kg": 24880.0,
        "masa_producto_final_kg": 24650.0,
        "merma_real_pct": 1.40,
        "merma_tolerada_pct": 1.5,
        "costo_kg_gs": 8500,
        "valor_lote_esperado_gs": 212500000,
        "perdida_merma_total_gs": 2975000,
        "desvio_sobre_tolerancia_gs": 0,
        "sensor_sospechoso": "Ninguno (Dentro de Norma)",
        "estado_auditoria": "APROBADO_CONFORME",
        "dictamen_auditor": "Merma de 1.40% dentro del umbral de 1.50%. Conciliación aceptada.",
        "auditor_firmante": "Lic. Marta Giménez"
    },
    {
        "lote_id": "LOT-2026-802",
        "producto": "Jugo de Naranja Aséptico 200ml",
        "fecha_cierre": "2026-10-16 11:15",
        "masa_erp_almacen_kg": 18000.0,
        "masa_mes_caudalimetro_kg": 17200.0,
        "masa_producto_final_kg": 17350.0,
        "merma_real_pct": 3.61,
        "merma_tolerada_pct": 1.5,
        "costo_kg_gs": 9200,
        "valor_lote_esperado_gs": 165600000,
        "perdida_merma_total_gs": 5980000,
        "desvio_sobre_tolerancia_gs": 3496000,
        "sensor_sospechoso": "Caudalímetro Masivo Coriolis FIT-201 (Deriva +4.2%)",
        "estado_auditoria": "BLOQUEADO_RECALIBRACION",
        "dictamen_auditor": "Desvío severo de masa. Se sospechan burbujas de aire en sensor Coriolis.",
        "auditor_firmante": "Ing. Roberto Franco"
    },
    {
        "lote_id": "LOT-2026-803",
        "producto": "Agua Mineralizada Sin Gas 500ml PET",
        "fecha_cierre": "2026-10-17 14:00",
        "masa_erp_almacen_kg": 45000.0,
        "masa_mes_caudalimetro_kg": 44800.0,
        "masa_producto_final_kg": 44450.0,
        "merma_real_pct": 1.22,
        "merma_tolerada_pct": 1.5,
        "costo_kg_gs": 2800,
        "valor_lote_esperado_gs": 126000000,
        "perdida_merma_total_gs": 1540000,
        "desvio_sobre_tolerancia_gs": 0,
        "sensor_sospechoso": "Ninguno (Dentro de Norma)",
        "estado_auditoria": "APROBADO_CONFORME",
        "dictamen_auditor": "Operación nominal. Lote despachado a centro logístico.",
        "auditor_firmante": "Lic. Marta Giménez"
    },
    {
        "lote_id": "LOT-2026-804",
        "producto": "Bebida Isotónica Citrus 600ml PET",
        "fecha_cierre": "2026-10-18 16:45",
        "masa_erp_almacen_kg": 32000.0,
        "masa_mes_caudalimetro_kg": 31100.0,
        "masa_producto_final_kg": 30900.0,
        "merma_real_pct": 3.44,
        "merma_tolerada_pct": 1.5,
        "costo_kg_gs": 7600,
        "valor_lote_esperado_gs": 243200000,
        "perdida_merma_total_gs": 8360000,
        "desvio_sobre_tolerancia_gs": 4712000,
        "sensor_sospechoso": "Válvula de Llenado Dosificadora V-12",
        "estado_auditoria": "PENDIENTE",
        "dictamen_auditor": "Pendiente de dictamen de aseguramiento de calidad.",
        "auditor_firmante": "Sin asignar"
    },
    {
        "lote_id": "LOT-2026-805",
        "producto": "Té Helado Durazno 1.5L PET",
        "fecha_cierre": "2026-10-19 09:20",
        "masa_erp_almacen_kg": 28000.0,
        "masa_mes_caudalimetro_kg": 27850.0,
        "masa_producto_final_kg": 27620.0,
        "merma_real_pct": 1.36,
        "merma_tolerada_pct": 1.5,
        "costo_kg_gs": 6400,
        "valor_lote_esperado_gs": 179200000,
        "perdida_merma_total_gs": 2432000,
        "desvio_sobre_tolerancia_gs": 0,
        "sensor_sospechoso": "Ninguno (Dentro de Norma)",
        "estado_auditoria": "APROBADO_CONFORME",
        "dictamen_auditor": "Aprobado por sistema automático ERP.",
        "auditor_firmante": "Lic. Marta Giménez"
    },
    {
        "lote_id": "LOT-2026-806",
        "producto": "Concentrado Base Guaraná 50L Tambor",
        "fecha_cierre": "2026-10-20 12:10",
        "masa_erp_almacen_kg": 15000.0,
        "masa_mes_caudalimetro_kg": 14250.0,
        "masa_producto_final_kg": 14320.0,
        "merma_real_pct": 4.53,
        "merma_tolerada_pct": 1.5,
        "costo_kg_gs": 18500,
        "valor_lote_esperado_gs": 277500000,
        "perdida_merma_total_gs": 12580000,
        "desvio_sobre_tolerancia_gs": 8417500,
        "sensor_sospechoso": "Báscula Celda de Carga W-03 (Descalibrada)",
        "estado_auditoria": "PENDIENTE",
        "dictamen_auditor": "Alerta financiera: pérdida de ₲ 8.417.500 por encima de la tolerancia admisible.",
        "auditor_firmante": "Sin asignar"
    },
    {
        "lote_id": "LOT-2026-807",
        "producto": "Jugo de Manzana Aséptico 1L Tetra",
        "fecha_cierre": "2026-10-21 07:40",
        "masa_erp_almacen_kg": 22000.0,
        "masa_mes_caudalimetro_kg": 21890.0,
        "masa_producto_final_kg": 21710.0,
        "merma_real_pct": 1.32,
        "merma_tolerada_pct": 1.5,
        "costo_kg_gs": 8900,
        "valor_lote_esperado_gs": 195800000,
        "perdida_merma_total_gs": 2581000,
        "desvio_sobre_tolerancia_gs": 0,
        "sensor_sospechoso": "Ninguno (Dentro de Norma)",
        "estado_auditoria": "APROBADO_CONFORME",
        "dictamen_auditor": "Aprobado dentro del límite de control estadístico.",
        "auditor_firmante": "Lic. Marta Giménez"
    },
    {
        "lote_id": "LOT-2026-808",
        "producto": "Pulpa Aséptica Mango 200L",
        "fecha_cierre": "2026-10-21 17:30",
        "masa_erp_almacen_kg": 35000.0,
        "masa_mes_caudalimetro_kg": 33900.0,
        "masa_producto_final_kg": 33850.0,
        "merma_real_pct": 3.29,
        "merma_tolerada_pct": 1.5,
        "costo_kg_gs": 14200,
        "valor_lote_esperado_gs": 497000000,
        "perdida_merma_total_gs": 16330000,
        "desvio_sobre_tolerancia_gs": 8875000,
        "sensor_sospechoso": "Transmisor de Flujo Electromagnético FIT-305",
        "estado_auditoria": "PENDIENTE",
        "dictamen_auditor": "En proceso de auditoría por discrepancia física vs fiscal.",
        "auditor_firmante": "Sin asignar"
    }
]

dictamenes_historial_db: List[Dict[str, Any]] = []


def calcular_resumen_conciliacion() -> Dict[str, Any]:
    """Calcula los totales de balance de masa y pérdida por mermas en Guaraníes."""
    total_lotes = len(lotes_conciliacion_db)
    lotes_con_anomalia = sum(1 for l in lotes_conciliacion_db if l["merma_real_pct"] > l["merma_tolerada_pct"])
    valor_total_produccion_gs = sum(l["valor_lote_esperado_gs"] for l in lotes_conciliacion_db)
    perdida_total_mermas_gs = sum(l["perdida_merma_total_gs"] for l in lotes_conciliacion_db)
    desvio_auditable_no_justificado_gs = sum(l["desvio_sobre_tolerancia_gs"] for l in lotes_conciliacion_db)

    return {
        "total_lotes": total_lotes,
        "lotes_con_anomalia": lotes_con_anomalia,
        "valor_total_produccion_gs": valor_total_produccion_gs,
        "perdida_total_mermas_gs": perdida_total_mermas_gs,
        "desvio_auditable_no_justificado_gs": desvio_auditable_no_justificado_gs
    }


@app.get("/api/admin/conciliacion-lotes", summary="Conciliación de masa MES vs. ERP y auditoría de desvíos")
async def get_conciliacion_lotes(
    estado_filtro: str = Query("TODOS", description="TODOS | PENDIENTE | APROBADO_CONFORME | BLOQUEADO_RECALIBRACION")
):
    """
    Retorna los 8 lotes industriales con su balance de masa, pérdidas financieras en ₲,
    resumen contable y puntos de serie para LayerChart.
    """
    if estado_filtro != "TODOS":
        lotes_retornados = [l for l in lotes_conciliacion_db if l["estado_auditoria"] == estado_filtro]
    else:
        lotes_retornados = lotes_conciliacion_db

    serie_lotes_chart = [
        {
            "idx": idx + 1,
            "lote_id": l["lote_id"],
            "merma_real_pct": l["merma_real_pct"],
            "merma_tolerada_pct": l["merma_tolerada_pct"],
            "desvio_millones_gs": round(l["desvio_sobre_tolerancia_gs"] / 1000000.0, 2)
        }
        for idx, l in enumerate(lotes_conciliacion_db)
    ]

    return {
        "estado_filtro": estado_filtro,
        "resumen_financiero": calcular_resumen_conciliacion(),
        "lotes": lotes_retornados,
        "serie_lotes_chart": serie_lotes_chart
    }


@app.post("/api/admin/conciliacion-lotes/dictamen", summary="Emitir dictamen contable/técnico sobre lote industrial")
async def emitir_dictamen_lote(payload: DictamenLoteRequest):
    """
    Actualiza el dictamen de un lote ('APROBADO_CONFORME' o 'BLOQUEADO_RECALIBRACION'),
    registra al auditor responsable y la causa raíz en la pista de auditoría industrial.
    """
    acciones_validas = ["APROBADO_CONFORME", "BLOQUEADO_RECALIBRACION"]
    if payload.accion not in acciones_validas:
        raise HTTPException(status_code=400, detail=f"Acción '{payload.accion}' no válida. Opciones: {acciones_validas}")

    lote = next((l for l in lotes_conciliacion_db if l["lote_id"] == payload.lote_id), None)
    if not lote:
        raise HTTPException(status_code=404, detail=f"Lote '{payload.lote_id}' no encontrado.")

    lote["estado_auditoria"] = payload.accion
    lote["dictamen_auditor"] = f"{payload.observacion} (Causa raíz: {payload.causa_raiz})"
    lote["auditor_firmante"] = payload.auditor

    registro_dictamen = {
        "id": f"DICT-{len(dictamenes_historial_db) + 1:03d}",
        "lote_id": payload.lote_id,
        "fecha_hora": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "accion": payload.accion,
        "auditor": payload.auditor,
        "causa_raiz": payload.causa_raiz,
        "observacion": payload.observacion
    }
    dictamenes_historial_db.insert(0, registro_dictamen)

    nivel = "WARN" if payload.accion == "BLOQUEADO_RECALIBRACION" else "INFO"
    registrar_evento(
        nivel=nivel,
        origen=f"AuditoríaERP/{payload.lote_id}",
        mensaje=f"Dictamen {payload.accion} emitido por {payload.auditor}: {payload.causa_raiz}"
    )

    return {
        "ok": True,
        "mensaje": f"Dictamen contable para {payload.lote_id} registrado como '{payload.accion}'.",
        "lote_actualizado": lote,
        "resumen_financiero": calcular_resumen_conciliacion()
    }


# ==============================================================================
# PUNTO DE ENTRADA PRINCIPAL
# ==============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8007, reload=True)
