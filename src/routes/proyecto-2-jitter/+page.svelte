<script>
	/**
	 * Proyecto 2: El Semáforo de Latencia y Jitter de Red
	 * Cátedra: Lenguajes de Programación Visual (LPV) — FIUNA
	 *
	 * Núcleo Pedagógico:
	 * - Determinismo Físico vs. Latencia Estadística TCP/IP
	 * - El Fenómeno del "Dato Congelado" (Silent Failure / Frozen Data)
	 * - Heartbeat Watchdog autónomo en el cliente con $effect (cleanup)
	 * - Diagnóstico reactivo de salud de enlace con $derived.by
	 * - Proyección temporal de alta cadencia con LayerChart y $state.raw
	 */
	import { FASTAPI_BASE_URL, UMBRALES_JITTER_MS } from '$lib/config.js';
	import { Chart, Svg, Spline, Axis, Rule } from 'layerchart';
	import { scaleLinear } from 'd3-scale';
	import CodeViewer from '$lib/components/CodeViewer.svelte';

	// Umbrales de enlace estandarizados de cátedra (ms)
	const UMBRAL_AMBAR_MS = UMBRALES_JITTER_MS?.EN_LAZO_MAX ?? 150;
	const UMBRAL_ROJO_MS = UMBRALES_JITTER_MS?.DEGRADADO_MAX ?? 800;

	// Buffer de telemetría de alta frecuencia: se usa $state.raw para evitar proxies reactivos profundos
	let paquetes = $state.raw([]);

	// Estados reactivos fundamentales (Svelte 5 Runes)
	let ahora = $state(performance.now());
	let timestampUltimoPaquete = $state(performance.now());
	let jitterInstantaneo = $state(0);
	let deltaTAnterior = 100;
	let totalPaquetes = $state(0);
	let ultimoValor = $state(null);
	let unidad = $state('°C');
	let seqActual = $state(0);
	let modoRedRecibido = $state('nominal');
	let modoActivo = $state('nominal');
	let estadoConexion = $state('iniciando'); // 'conectado' | 'desconectado' | 'iniciando'
	let enviandoConfig = $state(false);
	let intentoConexion = $state(0);

	// Estados del subsistema de actuadores (prueba de enclavamiento SCADA)
	let potenciaCalefactorKw = $state(25);
	let valvulaRefrigeracionAbierta = $state(false);
	let mensajeActuador = $state('');

	// 1. MEDICIÓN CONTINUA DE Δt (Heartbeat Watchdog)
	// deltaT crece en cada tick del cliente aunque la red se congele por completo
	const deltaT = $derived(Math.max(0, Math.round(ahora - timestampUltimoPaquete)));

	// 2. SEMÁFORO DE SALUD DE ENLACE COMPUTADO CON $derived.by (Regla de Cátedra)
	const diagnosticoEnlace = $derived.by(() => {
		if (deltaT < UMBRAL_AMBAR_MS) {
			return {
				estado: 'verde',
				color: '#16a34a',
				claseBadge: 'is-success pulse-green',
				codigo: 'EN LAZO / TIEMPO REAL',
				icono: 'fa-circle-check',
				operacionSegura: true,
				descripcion: 'Cadencia determinista nominal (~100 ms). Supervisión confiable.'
			};
		} else if (deltaT <= UMBRAL_ROJO_MS) {
			return {
				estado: 'ambar',
				color: '#d97706',
				claseBadge: 'is-warning pulse-amber',
				codigo: 'DEGRADACIÓN / JITTER',
				icono: 'fa-triangle-exclamation',
				operacionSegura: true,
				descripcion: 'Varianza estadística en la red TCP/IP. La telemetría presenta retardo variable.'
			};
		} else {
			return {
				estado: 'rojo',
				color: '#dc2626',
				claseBadge: 'is-danger blink-red-critical',
				codigo: 'PÉRDIDA DE SINCRONIZACIÓN / STOP OPERATIVO',
				icono: 'fa-skull-crossbones',
				operacionSegura: false,
				descripcion:
					'Enlace caído o congelado. PROHIBIDO tomar decisiones con el valor en pantalla.'
			};
		}
	});

	// Métricas estadísticas derivadas del buffer para análisis mecatrónico
	const statsBuffer = $derived.by(() => {
		if (!paquetes || paquetes.length === 0) {
			return { media: 0, jitterRms: 0, maxDelta: 0, minDelta: 0, tasaHz: 0 };
		}
		const deltas = paquetes.map((p) => p.deltaMs || 0);
		const sum = deltas.reduce((acc, val) => acc + val, 0);
		const media = Math.round(sum / deltas.length);
		const maxDelta = Math.max(...deltas);
		const minDelta = Math.min(...deltas);
		const varianza = deltas.reduce((acc, val) => acc + Math.pow(val - media, 2), 0) / deltas.length;
		const jitterRms = Math.round(Math.sqrt(varianza));
		const tasaHz = deltaT > 0 ? (1000 / Math.max(deltaT, 10)).toFixed(1) : '10.0';
		return { media, jitterRms, maxDelta, minDelta, tasaHz };
	});

	// Dominios dinámicos para LayerChart
	const xDomain = $derived.by(() => {
		if (!paquetes || paquetes.length < 2) return [0, 50];
		return [paquetes[0].seq, paquetes[paquetes.length - 1].seq];
	});

	const yDomain = $derived.by(() => {
		const maxRegistrado =
			paquetes && paquetes.length > 0
				? Math.max(1000, ...paquetes.map((p) => p.deltaMs || 0))
				: 1000;
		return [0, Math.ceil(maxRegistrado * 1.15)];
	});

	/**
	 * Procesa un paquete de telemetría entrante y actualiza el buffer circular
	 */
	function registrarLlegadaPaquete(data) {
		const recepcion = performance.now();
		const deltaLlegada = Math.round(recepcion - timestampUltimoPaquete);
		jitterInstantaneo = Math.round(Math.abs(deltaLlegada - deltaTAnterior));
		deltaTAnterior = deltaLlegada;
		timestampUltimoPaquete = recepcion;
		totalPaquetes++;

		if (data.valor !== undefined && !isNaN(Number(data.valor))) {
			ultimoValor = Number(data.valor);
		}
		if (data.unidad) unidad = data.unidad;
		if (data.seq !== undefined) seqActual = data.seq;
		if (data.modo_red) modoRedRecibido = data.modo_red;

		// Actualización inmutable del buffer de los últimos 50 paquetes
		const nuevoRegistro = {
			seq: data.seq ?? totalPaquetes,
			deltaMs: deltaLlegada,
			valor: ultimoValor
		};
		paquetes = [...paquetes.slice(-49), nuevoRegistro];
	}

	// 1.A. Efecto: Watchdog autónomo en el cliente (cada 25 ms) con limpieza automática
	$effect(() => {
		const interval = setInterval(() => {
			ahora = performance.now();
		}, 25);
		return () => clearInterval(interval);
	});

	// 1.B. Efecto: Conexión reactiva al stream SSE de FastAPI
	$effect(() => {
		intentoConexion; // reactividad para reintentar
		let es;
		let cancelado = false;
		estadoConexion = 'iniciando';

		try {
			es = new EventSource(`${FASTAPI_BASE_URL}/api/jitter/stream`);

			es.onopen = () => {
				if (cancelado) return;
				estadoConexion = 'conectado';
			};

			es.onmessage = (event) => {
				if (cancelado) return;
				try {
					const data = JSON.parse(event.data);
					registrarLlegadaPaquete(data);
				} catch (err) {
					console.error('Error al parsear payload SSE de jitter:', err);
				}
			};

			es.onerror = () => {
				if (cancelado) return;
				// Si EventSource falla o se corta, marcar desconectado sin activar ningún simulador local
				estadoConexion = 'desconectado';
			};
		} catch {
			estadoConexion = 'desconectado';
		}

		return () => {
			cancelado = true;
			if (es) es.close();
		};
	});

	/**
	 * Inyección de perturbaciones en FastAPI (POST /api/jitter/config)
	 */
	async function cambiarModoRed(nuevoModo) {
		enviandoConfig = true;
		try {
			const res = await fetch(`${FASTAPI_BASE_URL}/api/jitter/config`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ modo: nuevoModo })
			});
			if (res.ok) {
				const datos = await res.json();
				if (datos.modo_red_jitter) {
					modoActivo = datos.modo_red_jitter;
				} else if (datos.modo_activo) {
					modoActivo = datos.modo_activo;
				} else {
					modoActivo = nuevoModo;
				}
			} else {
				console.error('Error en POST /api/jitter/config:', res.status, res.statusText);
			}
		} catch (err) {
			console.error('Error al conectar con POST /api/jitter/config en FastAPI:', err);
		} finally {
			enviandoConfig = false;
		}
	}

	/**
	 * Acciones sobre los actuadores de planta (Sujetos a Enclavamiento por Watchdog)
	 */
	function subirPotencia() {
		if (!diagnosticoEnlace.operacionSegura) return;
		potenciaCalefactorKw = Math.min(100, potenciaCalefactorKw + 5);
		mensajeActuador = `✅ Potencia aumentada a ${potenciaCalefactorKw} kW`;
		setTimeout(() => (mensajeActuador = ''), 2500);
	}

	function bajarPotencia() {
		if (!diagnosticoEnlace.operacionSegura) return;
		potenciaCalefactorKw = Math.max(0, potenciaCalefactorKw - 5);
		mensajeActuador = `✅ Potencia reducida a ${potenciaCalefactorKw} kW`;
		setTimeout(() => (mensajeActuador = ''), 2500);
	}

	function alternarRefrigeracion() {
		if (!diagnosticoEnlace.operacionSegura) return;
		valvulaRefrigeracionAbierta = !valvulaRefrigeracionAbierta;
		mensajeActuador = valvulaRefrigeracionAbierta
			? '❄️ Válvula criogénica ABIERTA al 100%'
			: '🔒 Válvula criogénica CERRADA';
		setTimeout(() => (mensajeActuador = ''), 2500);
	}

	// Archivos didácticos para el componente pedagógico CodeViewer
	const archivosPedagogicos = [
		{
			nombre: 'HeartbeatWatchdog.svelte',
			lenguaje: 'svelte',
			descripcion:
				'Watchdog autónomo del cliente Svelte 5. Mide continuamente Δt = ahora - timestampUltimoPaquete mediante un temporizador rápido de 25 ms con cleanup garantizado en $effect.',
			codigo: `<script>
  import { FASTAPI_BASE_URL, UMBRALES_JITTER_MS } from '$lib/config.js';

  let timestampUltimoPaquete = $state(performance.now());
  let ahora = $state(performance.now());
  let jitterInstantaneo = $state(0);
  let deltaTAnterior = 100;
  let paquetes = $state.raw([]); // Buffer circular de alta frecuencia

  // Δt crece continuamente en el cliente, incluso ante el corte total del socket
  const deltaT = $derived(Math.max(0, Math.round(ahora - timestampUltimoPaquete)));

  // 1. Recepción continua de telemetría por Server-Sent Events (SSE)
  $effect(() => {
    const es = new EventSource(\`\${FASTAPI_BASE_URL}/api/jitter/stream\`);

    es.onmessage = (event) => {
      const data = JSON.parse(event.data);
      const recepcion = performance.now();
      const deltaLlegada = Math.round(recepcion - timestampUltimoPaquete);
      jitterInstantaneo = Math.round(Math.abs(deltaLlegada - deltaTAnterior));
      deltaTAnterior = deltaLlegada;
      timestampUltimoPaquete = recepcion;

      // Actualización inmutable sin costo de proxies profundos
      paquetes = [...paquetes.slice(-49), { seq: data.seq, deltaMs: deltaLlegada }];
    };

    return () => es.close(); // Cleanup automático al desmontar o re-ejecutar
  });

  // 2. Temporizador rápido autónomo (Watchdog Tick)
  $effect(() => {
    const timer = setInterval(() => {
      ahora = performance.now();
    }, 25);
    return () => clearInterval(timer); // Cleanup obligatorio
  });
<\/script>`
		},
		{
			nombre: 'SemaforoEnlace.svelte',
			lenguaje: 'svelte',
			descripcion:
				'Evaluación reactiva pura con $derived.by y enclavamiento de seguridad mecatrónica (IEC 61508 / SCADA Safety Interlock). Prohíbe actuar cuando el dato está congelado.',
			codigo: `<script>
  // Diagnóstico tri-estado de salud del enlace TCP/IP
  const diagnosticoEnlace = $derived.by(() => {
    if (deltaT < 150) {
      return {
        estado: 'verde',
        claseBadge: 'is-success pulse-green',
        codigo: 'EN LAZO / TIEMPO REAL',
        icono: 'fa-circle-check',
        operacionSegura: true,
        descripcion: 'Cadencia determinista nominal (~100 ms). Supervisión confiable.'
      };
    } else if (deltaT <= 800) {
      return {
        estado: 'ambar',
        claseBadge: 'is-warning pulse-amber',
        codigo: 'DEGRADACIÓN / JITTER',
        icono: 'fa-triangle-exclamation',
        operacionSegura: true,
        descripcion: 'Varianza estadística en la red TCP/IP. La telemetría presenta retardo variable.'
      };
    } else {
      return {
        estado: 'rojo',
        claseBadge: 'is-danger blink-red-critical',
        codigo: 'PÉRDIDA DE SINCRONIZACIÓN / STOP OPERATIVO',
        icono: 'fa-skull-crossbones',
        operacionSegura: false,
        descripcion: 'Enlace caído o congelado. PROHIBIDO tomar decisiones con el valor en pantalla.'
      };
    }
  });
<\/script>

<!-- Enclavamiento de Seguridad: Botones inhabilitados ante pérdida de sincronización -->
<button
  class="button is-danger"
  disabled={!diagnosticoEnlace.operacionSegura}
  onclick={aumentarCalefaccion}
>
  {#if !diagnosticoEnlace.operacionSegura}
    <i class="fa-solid fa-lock mr-2"></i> Mando Inhabilitado (Dato Congelado)
  {:else}
    <i class="fa-solid fa-fire mr-2"></i> Calentar Reactor (+5 kW)
  {/if}
</button>`
		},
		{
			nombre: 'fastapi_jitter_stream.py',
			lenguaje: 'python',
			descripcion:
				'Servidor FastAPI con endpoint de control POST /api/jitter/config y generador SSE GET /api/jitter/stream simulando perturbaciones de enlace físico.',
			codigo: `from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import asyncio
import json
import random
import time

app = FastAPI(title="Simulador de Enlace SCADA")

class ConfigRed(BaseModel):
    modo: str  # 'nominal' | 'jitter_moderado' | 'micro_cortes' | 'cable_desconectado'

estado_canal = {"modo": "nominal", "seq": 0, "temp_reactor": 72.4}

@app.post("/api/jitter/config")
async def config_canal(cfg: ConfigRed):
    estado_canal["modo"] = cfg.modo
    return {"status": "ok", "modo_activo": cfg.modo}

@app.get("/api/jitter/stream")
async def stream_telemetria(request: Request):
    async def generador():
        while True:
            if await request.is_disconnected():
                break

            modo = estado_canal["modo"]

            if modo == "cable_desconectado":
                # Silencio total: el socket permanece abierto pero sin tráfico
                await asyncio.sleep(1.0)
                continue

            elif modo == "micro_cortes":
                # Ráfagas normales alternadas con cortes severos > 900 ms
                retardo = random.uniform(0.95, 1.6) if random.random() < 0.28 else random.uniform(0.08, 0.12)

            elif modo == "jitter_moderado":
                # Jitter estocástico típico de Wi-Fi congestionado (180 - 680 ms)
                retardo = random.uniform(0.18, 0.68)

            else:  # nominal
                # Cadencia cuasi-determinista isócrona (~100 ms)
                retardo = random.uniform(0.095, 0.105)

            await asyncio.sleep(retardo)

            estado_canal["seq"] += 1
            estado_canal["temp_reactor"] += random.uniform(-0.15, 0.15)

            payload = {
                "seq": estado_canal["seq"],
                "timestamp_emision": time.time(),
                "valor": round(estado_canal["temp_reactor"], 2),
                "unidad": "°C",
                "modo_red": modo,
                "latencia_estimada_ms": round(retardo * 1000, 1)
            }
            yield f"data: {json.dumps(payload)}\\n\\n"

    return StreamingResponse(generador(), media_type="text/event-stream")`
		}
	];
</script>

<svelte:head>
	<title>Proyecto 2: El Semáforo de Latencia y Jitter — FIUNA LPV</title>
</svelte:head>

<!-- Migas de Pan de Navegación -->
<nav class="breadcrumb has-succeeds-separator is-small mb-4" aria-label="breadcrumbs">
	<ul>
		<li><a href="/">Inicio</a></li>
		<li><a href="/">Laboratorios</a></li>
		<li class="is-active">
			<a href="/proyecto-2-jitter" aria-current="page">2. Semáforo de Jitter</a>
		</li>
	</ul>
</nav>

<!-- Encabezado Principal del Proyecto -->
<header class="mb-5">
	<div class="is-flex is-align-items-center mb-2" style="gap: 0.5rem; flex-wrap: wrap;">
		<span class="tag is-warning is-dark has-text-weight-bold">PROYECTO 02</span>
		<span class="tag is-info is-light">Svelte 5 Runes</span>
		<span class="tag is-dark is-family-code">FastAPI SSE</span>
		<span class="tag is-primary is-light">LayerChart</span>
		<span class="tag is-danger is-light">Seguridad Funcional IEC 61508</span>
	</div>

	<h1 class="title is-2 mb-2">
		<i class="fa-solid fa-traffic-light has-text-warning mr-2"></i>
		El Semáforo de Latencia y Jitter de Red
	</h1>
	<p class="subtitle is-5 has-text-grey">
		<strong>Determinismo Físico vs. Latencia Estadística TCP/IP:</strong> Demostración en tiempo real
		del peligro del <em>"Dato Congelado"</em> y cómo implementar un <strong>Heartbeat Watchdog</strong>
		autónomo en el cliente para enclavar mandos de planta ante pérdidas de sincronización.
	</p>
</header>

<!-- Barra de Estado de Conexión al Backend FastAPI -->
<div class="notification p-3 mb-5 is-light is-flex is-align-items-center is-justify-content-between" style="border: 1px solid #cbd5e1; border-radius: 8px;">
	<div class="is-flex is-align-items-center" style="gap: 0.75rem; flex-wrap: wrap;">
		<span class="has-text-weight-bold is-size-7">
			<i class="fa-solid fa-server mr-1"></i> Backend FastAPI ({FASTAPI_BASE_URL}):
		</span>

		{#if estadoConexion === 'conectado'}
			<span class="tag is-success is-small">
				<i class="fa-solid fa-circle-check mr-1"></i> Stream SSE Conectado
			</span>
		{:else if estadoConexion === 'desconectado'}
			<span class="tag is-danger is-small">
				<i class="fa-solid fa-circle-xmark mr-1"></i> Desconectado de FastAPI
			</span>
		{:else}
			<span class="tag is-info is-small">
				<i class="fa-solid fa-spinner fa-spin mr-1"></i> Conectando...
			</span>
		{/if}

		<span class="tag is-dark is-small is-family-code">
			Canal activo: {modoActivo}
		</span>

		<span class="tag is-info is-light is-small is-family-code">
			GET {FASTAPI_BASE_URL}/api/jitter/stream &bull; POST {FASTAPI_BASE_URL}/api/jitter/config
		</span>
	</div>

	<div class="buttons are-small mb-0">
		<button
			type="button"
			class="button is-white is-outlined"
			onclick={() => {
				intentoConexion++;
				timestampUltimoPaquete = performance.now();
			}}
		>
			<i class="fa-solid fa-rotate mr-1"></i> Reintentar Conexión
		</button>
	</div>
</div>

<!-- ========================================================================= -->
<!-- FILA 1: NÚCLEO SCADA (Semáforo Industrial + Display Sensor + Enclavamiento) -->
<!-- ========================================================================= -->
<div class="columns is-multiline mb-5">
	<!-- Columna 1: El Semáforo SCADA Industrial Tri-Estado -->
	<div class="column is-12 is-4-desktop">
		<div class="card h-100 scada-panel">
			<header class="card-header px-4 py-3 scada-panel-header">
				<p class="card-header-title is-size-6 mb-0">
					<i class="fa-solid fa-traffic-light mr-2 has-text-warning"></i>
					Semáforo de Salud de Enlace
				</p>
				<span class="tag is-small is-dark is-family-code">Δt: {deltaT} ms</span>
			</header>

			<div class="card-content">
				<div class="is-flex is-align-items-center is-justify-content-center mb-4">
					<!-- Gabinete Físico del Semáforo Industrial -->
					<div class="semaforo-industrial">
						<!-- Foco Rojo: Stop Operativo / Pérdida de Sincronización -->
						<div
							class="foco rojo {diagnosticoEnlace.estado === 'rojo'
								? 'activo blink-red-critical'
								: 'inactivo'}"
							title="Rojo: Pérdida de sincronización (Δt > 800 ms)"
						>
							<i class="fa-solid fa-skull-crossbones"></i>
						</div>

						<!-- Foco Ámbar: Degradación / Jitter Severo -->
						<div
							class="foco ambar {diagnosticoEnlace.estado === 'ambar'
								? 'activo pulse-amber'
								: 'inactivo'}"
							title="Ámbar: Degradación estadística (150 ms <= Δt <= 800 ms)"
						>
							<i class="fa-solid fa-triangle-exclamation"></i>
						</div>

						<!-- Foco Verde: Tiempo Real / En Lazo Nominal -->
						<div
							class="foco verde {diagnosticoEnlace.estado === 'verde'
								? 'activo pulse-green'
								: 'inactivo'}"
							title="Verde: Transmisión determinista nominal (Δt < 150 ms)"
						>
							<i class="fa-solid fa-circle-check"></i>
						</div>
					</div>

					<!-- Indicadores Numéricos del Watchdog -->
					<div class="ml-4 is-flex-grow-1">
						<div class="mb-3">
							<span class="is-size-7 has-text-grey is-uppercase has-text-weight-bold">
								Diagnóstico $derived.by:
							</span>
							<div class="tag is-medium mt-1 is-fullwidth {diagnosticoEnlace.claseBadge}">
								<i class="fa-solid {diagnosticoEnlace.icono} mr-2"></i>
								<strong>{diagnosticoEnlace.codigo}</strong>
							</div>
						</div>

						<div class="notification p-2 is-size-7 mb-2" style="background: #f8fafc; border-left: 3px solid {diagnosticoEnlace.color};">
							{diagnosticoEnlace.descripcion}
						</div>

						<div class="is-flex is-justify-content-between is-size-7 has-text-grey-dark">
							<span>Jitter Instantáneo:</span>
							<strong class="is-family-code">±{jitterInstantaneo} ms</strong>
						</div>
						<div class="is-flex is-justify-content-between is-size-7 has-text-grey-dark">
							<span>Frecuencia estimada:</span>
							<strong class="is-family-code">{statsBuffer.tasaHz} Hz</strong>
						</div>
					</div>
				</div>

				<div class="p-3" style="background: #f1f5f9; border-radius: 6px; font-size: 0.78rem;">
					<i class="fa-solid fa-info-circle mr-1 has-text-info"></i>
					<strong>Regla de Decisión Cátedra:</strong>
					Verde: <code>&lt; 150 ms</code> | Ámbar: <code>150–800 ms</code> | Rojo Crítico:
					<code>&gt; 800 ms</code>.
				</div>
			</div>
		</div>
	</div>

	<!-- Columna 2: Instrumento de Telemetría (El Mito del Dato Congelado) -->
	<div class="column is-12 is-4-desktop">
		<div class="card h-100 scada-panel">
			<header class="card-header px-4 py-3 scada-panel-header">
				<p class="card-header-title is-size-6 mb-0">
					<i class="fa-solid fa-temperature-arrow-up mr-2 has-text-danger"></i>
					Temperatura del Reactor Térmico
				</p>
				<span class="tag is-small {deltaT > UMBRAL_ROJO_MS ? 'is-danger' : 'is-link'}">
					Paquete #{seqActual}
				</span>
			</header>

			<div class="card-content is-flex is-flex-direction-column is-justify-content-between">
				<!-- Pantalla Digital LCD Industrial -->
				<div class="lcd-housing mb-3 {deltaT > UMBRAL_ROJO_MS ? 'lcd-frozen' : ''}">
					<div class="is-flex is-justify-content-between is-align-items-center mb-1">
						<span class="lcd-label">
							<i class="fa-solid fa-microchip mr-1"></i> RTD PT100 — LAZO #04
						</span>
						<span class="lcd-live-badge {deltaT > UMBRAL_ROJO_MS ? 'has-text-danger' : 'has-text-success'}">
							{#if deltaT > UMBRAL_ROJO_MS}
								<i class="fa-solid fa-circle-pause mr-1"></i> CONGELADO
							{:else}
								<i class="fa-solid fa-wave-square mr-1"></i> EN VIVO
							{/if}
						</span>
					</div>

					<div class="is-flex is-align-items-baseline is-justify-content-center py-2">
						<span class="lcd-value">{ultimoValor !== null ? ultimoValor.toFixed(1) : '--.-'}</span>
						<span class="lcd-unit ml-2">{unidad}</span>
					</div>

					<div class="is-flex is-justify-content-between is-size-7 mt-1 has-text-grey-light">
						<span>Watchdog local: <strong>{deltaT} ms</strong></span>
						<span>Total rx: <strong>{totalPaquetes}</strong></span>
					</div>
				</div>

				<!-- ALERTA PARPADEANTE DE DATO CONGELADO (Requisito Crítico Pedagógico) -->
				{#if deltaT > UMBRAL_ROJO_MS}
					<div
						class="notification is-danger is-light p-3 mb-3 blink-red-critical"
						style="border: 2px solid #dc2626; border-radius: 8px;"
					>
						<p class="has-text-weight-bold is-size-6 mb-1">
							<i class="fa-solid fa-triangle-exclamation mr-1"></i>
							⚠️ DATO CONGELADO HACE {(deltaT / 1000).toFixed(1)}s — LECTURA OBSOLETA
						</p>
						<p class="is-size-7" style="line-height: 1.35;">
							El valor en pantalla <strong>({ultimoValor !== null ? ultimoValor.toFixed(1) : '--.-'} °C)</strong> no cae a cero:
							permanece clavado en memoria. Es un <em>falso positivo de estabilidad</em>.
						</p>
					</div>
				{:else}
					<div class="notification is-success is-light p-2 mb-3 is-size-7">
						<i class="fa-solid fa-check-double mr-1"></i>
						Lectura fresca sincronizada con el generador físico del reactor.
					</div>
				{/if}

				<div class="is-size-7 has-text-grey" style="background: #f8fafc; padding: 0.5rem; border-radius: 6px;">
					<strong>Mito Desmentido:</strong> En TCP/IP, ante un corte de cable el valor numérico
					<strong>NO desaparece ni cae a 0.0 °C</strong>. Sin watchdog cliente, el operador cree que el
					reactor está estable mientras puede estar fundiéndose.
				</div>
			</div>
		</div>
	</div>

	<!-- Columna 3: Enclavamiento SCADA de Mandos Operativos (Safety Interlock) -->
	<div class="column is-12 is-4-desktop">
		<div class="card h-100 scada-panel">
			<header class="card-header px-4 py-3 scada-panel-header">
				<p class="card-header-title is-size-6 mb-0">
					<i class="fa-solid fa-shield-halved mr-2 has-text-info"></i>
					Enclavamiento SCADA (IEC 61508)
				</p>
				<span class="tag is-small {diagnosticoEnlace.operacionSegura ? 'is-success' : 'is-danger'}">
					{#if diagnosticoEnlace.operacionSegura}
						<i class="fa-solid fa-unlock mr-1"></i> Desbloqueado
					{:else}
						<i class="fa-solid fa-lock mr-1"></i> Interlock Activo
					{/if}
				</span>
			</header>

			<div class="card-content is-flex is-flex-direction-column is-justify-content-between">
				<div>
					<p class="is-size-7 has-text-grey mb-3">
						Prueba de seguridad: los actuadores de potencia están sujetos a
						<code>operacionSegura === true</code>. Si la red se degrada a Rojo, toda orden física se
						bloquea para evitar operación a ciegas.
					</p>

					<!-- Estado de los Actuadores -->
					<div class="box p-3 mb-3" style="background: #f8fafc; border: 1px solid #e2e8f0;">
						<div class="is-flex is-justify-content-between is-align-items-center mb-2">
							<span class="is-size-7">Potencia Calefactor:</span>
							<span class="tag is-dark is-family-code">{potenciaCalefactorKw} kW</span>
						</div>
						<progress
							class="progress is-danger is-small mb-3"
							value={potenciaCalefactorKw}
							max="100"
						></progress>

						<div class="is-flex is-justify-content-between is-align-items-center">
							<span class="is-size-7">Válvula Refrigerante:</span>
							<span class="tag {valvulaRefrigeracionAbierta ? 'is-info' : 'is-light'}">
								{valvulaRefrigeracionAbierta ? 'ABIERTA 100%' : 'CERRADA'}
							</span>
						</div>
					</div>

					<!-- Botones de Mando Operativo -->
					<div class="buttons are-small mb-2">
						<button
							type="button"
							class="button is-danger is-outlined is-fullwidth"
							disabled={!diagnosticoEnlace.operacionSegura}
							onclick={subirPotencia}
						>
							<i class="fa-solid fa-fire mr-1"></i> Aumentar Calefactor (+5 kW)
						</button>

						<button
							type="button"
							class="button is-dark is-outlined is-fullwidth"
							disabled={!diagnosticoEnlace.operacionSegura}
							onclick={bajarPotencia}
						>
							<i class="fa-solid fa-arrow-down mr-1"></i> Reducir Calefactor (-5 kW)
						</button>

						<button
							type="button"
							class="button is-info is-outlined is-fullwidth"
							disabled={!diagnosticoEnlace.operacionSegura}
							onclick={alternarRefrigeracion}
						>
							<i class="fa-solid fa-snowflake mr-1"></i>
							{valvulaRefrigeracionAbierta ? 'Cerrar Refrigeración' : 'Inyectar Refrigerante'}
						</button>
					</div>

					{#if mensajeActuador}
						<div class="notification is-info is-light p-2 is-size-7 mb-2">
							{mensajeActuador}
						</div>
					{/if}
				</div>

				{#if !diagnosticoEnlace.operacionSegura}
					<div class="notification is-danger is-light p-2 is-size-7" style="border: 1px dashed #dc2626;">
						<i class="fa-solid fa-ban mr-1"></i>
						<strong>MANDOS BLOQUEADOS:</strong> Watchdog vencido ({deltaT} ms &gt; 800 ms). Se prohíbe
						actuar sin verificación física.
					</div>
				{:else}
					<div class="notification is-success is-light p-2 is-size-7">
						<i class="fa-solid fa-shield-check mr-1"></i>
						Enlace certificado para mando interactivo por operador.
					</div>
				{/if}
			</div>
		</div>
	</div>
</div>

<!-- ========================================================================= -->
<!-- FILA 2: INYECTOR DE PERTURBACIONES EN FASTAPI (POST /api/jitter/config)   -->
<!-- ========================================================================= -->
<div class="card mb-5 scada-panel">
	<header class="card-header px-4 py-3 scada-panel-header">
		<p class="card-header-title is-size-6 mb-0">
			<i class="fa-solid fa-network-wired mr-2 has-text-link"></i>
			Inyector de Perturbaciones de Red en FastAPI (POST /api/jitter/config)
		</p>
		<span class="tag is-info is-light">4 Escenarios Industriales</span>
	</header>

	<div class="card-content">
		<p class="is-size-7 has-text-grey mb-4">
			Selecciona el modo de perturbación para inyectar anomalías de canal en el servidor FastAPI.
			Observa la respuesta inmediata del semáforo y la gráfica de latencia.
		</p>

		<div class="columns is-multiline">
			<!-- Botón 1: Nominal -->
			<div class="column is-6 is-3-desktop">
				<button
					type="button"
					class="button is-fullwidth h-100 p-3 is-flex is-flex-direction-column is-justify-content-between {modoActivo ===
					'nominal'
						? 'is-success'
						: 'is-white'}"
					style="border: 2px solid {modoActivo === 'nominal' ? '#16a34a' : '#cbd5e1'}; min-height: 110px;"
					disabled={enviandoConfig}
					onclick={() => cambiarModoRed('nominal')}
				>
					<div class="has-text-left w-100">
						<span class="has-text-weight-bold is-size-6">
							🟢 1. Canal Determinista Nominal
						</span>
						<p class="is-size-7 mt-1" style="opacity: 0.9;">
							Cadencia regular isócrona (~100 ms). Estado Verde en lazo.
						</p>
					</div>
					<div class="w-100 is-flex is-justify-content-between is-size-7 mt-2">
						<span class="tag is-light is-small">Δt ≈ 100 ms</span>
						{#if modoActivo === 'nominal'}
							<span class="tag is-dark is-small">ACTIVO</span>
						{/if}
					</div>
				</button>
			</div>

			<!-- Botón 2: Jitter Moderado -->
			<div class="column is-6 is-3-desktop">
				<button
					type="button"
					class="button is-fullwidth h-100 p-3 is-flex is-flex-direction-column is-justify-content-between {modoActivo ===
					'jitter_moderado'
						? 'is-warning'
						: 'is-white'}"
					style="border: 2px solid {modoActivo === 'jitter_moderado' ? '#d97706' : '#cbd5e1'}; min-height: 110px;"
					disabled={enviandoConfig}
					onclick={() => cambiarModoRed('jitter_moderado')}
				>
					<div class="has-text-left w-100">
						<span class="has-text-weight-bold is-size-6">
							🟡 2. Jitter Wi-Fi Industrial
						</span>
						<p class="is-size-7 mt-1" style="opacity: 0.9;">
							Varianza estadística TCP/IP (180–680 ms). Semáforo en Ámbar.
						</p>
					</div>
					<div class="w-100 is-flex is-justify-content-between is-size-7 mt-2">
						<span class="tag is-light is-small">180–680 ms</span>
						{#if modoActivo === 'jitter_moderado'}
							<span class="tag is-dark is-small">ACTIVO</span>
						{/if}
					</div>
				</button>
			</div>

			<!-- Botón 3: Micro-cortes -->
			<div class="column is-6 is-3-desktop">
				<button
					type="button"
					class="button is-fullwidth h-100 p-3 is-flex is-flex-direction-column is-justify-content-between {modoActivo ===
					'micro_cortes'
						? 'is-danger is-light has-text-danger-dark'
						: 'is-white'}"
					style="border: 2px solid {modoActivo === 'micro_cortes' ? '#dc2626' : '#cbd5e1'}; min-height: 110px;"
					disabled={enviandoConfig}
					onclick={() => cambiarModoRed('micro_cortes')}
				>
					<div class="has-text-left w-100">
						<span class="has-text-weight-bold is-size-6">
							🟠 3. Micro-cortes Industriales
						</span>
						<p class="is-size-7 mt-1" style="opacity: 0.9;">
							Congestión de switch o EMI: pausas esporádicas &gt; 900 ms.
						</p>
					</div>
					<div class="w-100 is-flex is-justify-content-between is-size-7 mt-2">
						<span class="tag is-danger is-small">Pausas &gt; 900 ms</span>
						{#if modoActivo === 'micro_cortes'}
							<span class="tag is-danger is-small has-text-weight-bold">ACTIVO</span>
						{/if}
					</div>
				</button>
			</div>

			<!-- Botón 4: Cable Desconectado -->
			<div class="column is-6 is-3-desktop">
				<button
					type="button"
					class="button is-fullwidth h-100 p-3 is-flex is-flex-direction-column is-justify-content-between {modoActivo ===
					'cable_desconectado'
						? 'is-danger blink-red-critical'
						: 'is-white'}"
					style="border: 2px solid {modoActivo === 'cable_desconectado' ? '#dc2626' : '#cbd5e1'}; min-height: 110px;"
					disabled={enviandoConfig}
					onclick={() => cambiarModoRed('cable_desconectado')}
				>
					<div class="has-text-left w-100">
						<span class="has-text-weight-bold is-size-6">
							🔴 4. Cortar Cable Virtual
						</span>
						<p class="is-size-7 mt-1" style="opacity: 0.9;">
							Silencio total en el socket. Dato congelado y paro por watchdog.
						</p>
					</div>
					<div class="w-100 is-flex is-justify-content-between is-size-7 mt-2">
						<span class="tag is-dark is-small">Δt → ∞</span>
						{#if modoActivo === 'cable_desconectado'}
							<span class="tag is-warning is-small has-text-dark has-text-weight-bold">CABLE CORTADO</span>
						{/if}
					</div>
				</button>
			</div>
		</div>
	</div>
</div>

<!-- ========================================================================= -->
<!-- FILA 3: GRÁFICA DE LATENCIA Y JITTER CON LAYERCHART ($state.raw)          -->
<!-- ========================================================================= -->
<div class="card mb-5 scada-panel">
	<header class="card-header px-4 py-3 scada-panel-header is-justify-content-between is-align-items-center">
		<p class="card-header-title is-size-6 mb-0">
			<i class="fa-solid fa-chart-line mr-2 has-text-primary"></i>
			Perfil Temporal de Jitter y Umbrales Críticos (Últimos 50 Paquetes)
		</p>

		<!-- Leyenda de Umbrales LayerChart -->
		<div class="is-flex is-align-items-center" style="gap: 0.75rem; font-size: 0.78rem;">
			<span class="is-flex is-align-items-center">
				<span class="legend-box" style="background: #16a34a;"></span>
				Nominal (&lt; 150 ms)
			</span>
			<span class="is-flex is-align-items-center">
				<span class="legend-line" style="border-top: 2px dashed #d97706;"></span>
				Alerta: 150 ms
			</span>
			<span class="is-flex is-align-items-center">
				<span class="legend-line" style="border-top: 2px dashed #dc2626;"></span>
				Paro: 800 ms
			</span>
		</div>
	</header>

	<div class="card-content">
		<!-- Contenedor Oficial de LayerChart especificado por Cátedra -->
		<div class="layerchart-box">
			{#if paquetes && paquetes.length > 1}
				<Chart
					data={paquetes}
					x="seq"
					y="deltaMs"
					xScale={scaleLinear()}
					yScale={scaleLinear()}
					yDomain={yDomain}
					xDomain={xDomain}
					padding={{ left: 52, bottom: 28, top: 12, right: 18 }}
				>
					<Svg>
						<Axis placement="left" grid rule />
						<Axis placement="bottom" grid rule />

						<!-- Líneas de Umbral Pedagógicas -->
						<Rule y={UMBRAL_AMBAR_MS} stroke="#d97706" strokeDasharray="4 4" strokeWidth={1.5} />
						<Rule y={UMBRAL_ROJO_MS} stroke="#dc2626" strokeDasharray="4 4" strokeWidth={2} />

						<!-- Trazo Reactivo de la Serie de Paquetes -->
						<Spline stroke="#2563eb" strokeWidth={2} />
					</Svg>
				</Chart>
			{:else}
				<div class="is-flex is-align-items-center is-justify-content-center h-100 has-text-grey">
					<i class="fa-solid fa-spinner fa-spin mr-2"></i> Adquiriendo telemetría inicial...
				</div>
			{/if}
		</div>

		<!-- Métricas Estadísticas del Buffer Circular -->
		<div class="columns is-multiline is-mobile mt-3 has-text-centered is-size-7">
			<div class="column is-3">
				<div class="p-2" style="background: #f8fafc; border-radius: 6px;">
					<span class="has-text-grey">Δt Promedio:</span>
					<div class="is-size-6 has-text-weight-bold is-family-code">{statsBuffer.media} ms</div>
				</div>
			</div>
			<div class="column is-3">
				<div class="p-2" style="background: #f8fafc; border-radius: 6px;">
					<span class="has-text-grey">Jitter RMS (σ):</span>
					<div class="is-size-6 has-text-weight-bold is-family-code">±{statsBuffer.jitterRms} ms</div>
				</div>
			</div>
			<div class="column is-3">
				<div class="p-2" style="background: #f8fafc; border-radius: 6px;">
					<span class="has-text-grey">Pico Máximo Δt:</span>
					<div class="is-size-6 has-text-weight-bold is-family-code has-text-danger">
						{statsBuffer.maxDelta} ms
					</div>
				</div>
			</div>
			<div class="column is-3">
				<div class="p-2" style="background: #f8fafc; border-radius: 6px;">
					<span class="has-text-grey">Frecuencia de Llegada:</span>
					<div class="is-size-6 has-text-weight-bold is-family-code has-text-link">
						{statsBuffer.tasaHz} Hz
					</div>
				</div>
			</div>
		</div>
	</div>
</div>

<!-- ========================================================================= -->
<!-- FILA 4: TARJETAS PEDAGÓGICAS DE CÁTEDRA (Conceptos de Mecatrónica)        -->
<!-- ========================================================================= -->
<div class="columns is-multiline mb-5">
	<div class="column is-12 is-4-desktop">
		<div class="concept-card p-4">
			<div>
				<div class="tag is-info is-light mb-2 has-text-weight-bold">
					<i class="fa-solid fa-network-wired mr-1"></i> BUS DETERMINISTA VS. TCP/IP
				</div>
				<h4 class="title is-6 mb-2">Ausencia de Determinismo en Protocolos Web</h4>
				<p class="is-size-7 has-text-grey">
					En un bus mecatrónico de campo (CAN Bus, EtherCAT, PROFINET), los paquetes arriban en
					ventanas isócronas garantizadas por silicio (&plusmn;1 &mu;s). En la pila Ethernet TCP/IP,
					la congestión de switches, el bufferbloat y la retransmisión introducen retardo estocástico
					(jitter). El frontend web nunca debe asumir cadencia constante.
				</p>
			</div>
			<div class="mt-3 is-size-7 has-text-link">
				<i class="fa-solid fa-book-bookmark mr-1"></i> Fundamento de Redes Industriales
			</div>
		</div>
	</div>

	<div class="column is-12 is-4-desktop">
		<div class="concept-card p-4">
			<div>
				<div class="tag is-danger is-light mb-2 has-text-weight-bold">
					<i class="fa-solid fa-icicles mr-1"></i> SILENT FAILURE
				</div>
				<h4 class="title is-6 mb-2">La Trampa del "Dato Congelado"</h4>
				<p class="is-size-7 has-text-grey">
					Si un cable de red se corta o un proceso remoto entra en deadlock, el socket TCP puede no
					enviar paquetes de terminación (RST/FIN). La variable de estado del frontend conserva el
					último número asignado. El operador interpreta erróneamente un sistema hiper-estable cuando en
					realidad está supervisando un "fantasma en memoria".
				</p>
			</div>
			<div class="mt-3 is-size-7 has-text-danger">
				<i class="fa-solid fa-triangle-exclamation mr-1"></i> Norma ISA-101 / Alarm Management
			</div>
		</div>
	</div>

	<div class="column is-12 is-4-desktop">
		<div class="concept-card p-4">
			<div>
				<div class="tag is-success is-light mb-2 has-text-weight-bold">
					<i class="fa-solid fa-heart-pulse mr-1"></i> WATCHDOG TICK
				</div>
				<h4 class="title is-6 mb-2">Heartbeat Watchdog en Svelte 5</h4>
				<p class="is-size-7 has-text-grey">
					La solución mecatrónica correcta es desacoplar la medición de tiempo del stream entrante. Un
					temporizador autónomo en <code>$effect</code> actualiza <code>ahora</code> cada 25 ms. De este
					modo, <code>deltaT = ahora - timestampUltimoPaquete</code> escala de manera continua sin
					importar si la red está en silencio, permitiendo al semáforo disparar la alarma y bloquear
					los mandos.
				</p>
			</div>
			<div class="mt-3 is-size-7 has-text-success">
				<i class="fa-solid fa-bolt mr-1"></i> Arquitectura Reactiva con Runes
			</div>
		</div>
	</div>
</div>

<!-- ========================================================================= -->
<!-- FILA 5: VISOR DE CÓDIGO FUENTE DIDÁCTICO (<CodeViewer>)                   -->
<!-- ========================================================================= -->
<CodeViewer
	titulo="Implementación Técnica: Watchdog, Semáforo y Servidor FastAPI SSE"
	archivos={archivosPedagogicos}
/>

<style>
	/* Gabinete y Paneles SCADA */
	.scada-panel {
		border: 1px solid #cbd5e1;
		border-radius: 10px;
		background: #ffffff;
		box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
	}

	.scada-panel-header {
		background: #f8fafc;
		border-bottom: 1px solid #e2e8f0;
	}

	/* Semáforo Industrial */
	.semaforo-industrial {
		background: #0f172a;
		border: 2px solid #334155;
		border-radius: 18px;
		padding: 12px 14px;
		display: flex;
		flex-direction: column;
		gap: 12px;
		box-shadow: 0 8px 16px rgba(15, 23, 42, 0.25);
	}

	.foco {
		width: 52px;
		height: 52px;
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 1.25rem;
		transition: all 0.25s ease;
	}

	.foco.inactivo {
		background: #1e293b;
		color: #475569;
		border: 1px solid #334155;
		box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.4);
	}

	.foco.rojo.activo {
		background: #dc2626;
		color: #ffffff;
		border: 2px solid #fca5a5;
	}

	.foco.ambar.activo {
		background: #d97706;
		color: #ffffff;
		border: 2px solid #fde047;
	}

	.foco.verde.activo {
		background: #16a34a;
		color: #ffffff;
		border: 2px solid #86efac;
	}

	/* Pantalla Digital LCD para el Sensor de Proceso */
	.lcd-housing {
		background: #020617;
		border: 2px solid #1e293b;
		border-radius: 10px;
		padding: 14px 16px;
		box-shadow: inset 0 2px 6px rgba(0, 0, 0, 0.8);
		position: relative;
		transition: border-color 0.3s ease;
	}

	.lcd-housing.lcd-frozen {
		border-color: #dc2626;
		box-shadow: inset 0 0 12px rgba(220, 38, 38, 0.4);
	}

	.lcd-label {
		font-family: monospace;
		font-size: 0.72rem;
		color: #94a3b8;
		letter-spacing: 0.05em;
	}

	.lcd-live-badge {
		font-family: monospace;
		font-size: 0.72rem;
		font-weight: 700;
	}

	.lcd-value {
		font-family: 'Fira Code', 'Courier New', monospace;
		font-size: 3.4rem;
		font-weight: 800;
		line-height: 1;
		color: #38bdf8;
		text-shadow: 0 0 10px rgba(56, 189, 248, 0.4);
	}

	.lcd-unit {
		font-family: 'Fira Code', monospace;
		font-size: 1.6rem;
		font-weight: 600;
		color: #64748b;
	}

	/* Leyenda para LayerChart */
	.legend-box {
		display: inline-block;
		width: 12px;
		height: 12px;
		border-radius: 2px;
		margin-right: 6px;
	}

	.legend-line {
		display: inline-block;
		width: 18px;
		height: 0;
		margin-right: 6px;
	}

	.w-100 {
		width: 100%;
	}
</style>
