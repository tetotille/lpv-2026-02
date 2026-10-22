<script>
	/**
	 * Vista Dinámica de Instrumentación y Calibración Remota (/sensores/[id])
	 * Utiliza LayerChart + $state.raw + use:enhance para telemetría a 60 fps y calibración sin recarga.
	 *
	 * Svelte 5 Runes: $props, $state, $state.raw, $derived, $effect
	 * Cátedra: Lenguajes de Programación Visual — FIUNA
	 */
	import { FASTAPI_BASE_URL } from '$lib/config.js';
	import { enhance } from '$app/forms';
	import { Chart, Svg, Spline, Area, Axis, Rule } from 'layerchart';
	import { scaleLinear } from 'd3-scale';
	import CodeViewer from '$lib/components/CodeViewer.svelte';

	let { data, form } = $props();

	// Sensor reactivo local sincronizado desde data de FastAPI
	let sensor = $state({
		id: 'TI-101',
		nombre: 'Transductor Industrial',
		nodo: '',
		modelo: '',
		unidad: '',
		valor_actual: 0,
		offset: 0,
		rango_min: 0,
		rango_max: 100,
		frecuencia_muestreo_hz: 10,
		descripcion: ''
	});

	let estadisticas = $state({
		minimo: 0,
		maximo: 0,
		promedio: 0,
		total_muestras: 0
	});

	// Variables para el formulario de calibración
	let formOffset = $state(0.0);
	let formRangoMax = $state(100.0);
	let formFrecuencia = $state(10);
	let guardando = $state(false);
	let mensajeFeedback = $state(null);

	// Sincronizar estado al cambiar la ruta o recibir nueva data SSR
	$effect(() => {
		if (!data.sensor) return;
		const s = data.sensor;
		sensor.id = s.id || data.sensorId;
		sensor.nombre = s.nombre || 'Transductor Industrial';
		sensor.nodo = s.nodo || '';
		sensor.modelo = s.modelo || '';
		sensor.unidad = s.unidad || '';
		sensor.valor_actual = Number(s.valor_actual ?? 0);
		sensor.offset = Number(s.offset ?? 0);
		sensor.rango_min = Number(s.rango_min ?? 0);
		sensor.rango_max = Number(s.rango_max ?? 100);
		sensor.frecuencia_muestreo_hz = Number(s.frecuencia_muestreo_hz ?? 10);
		sensor.descripcion = s.descripcion || '';

		estadisticas.minimo = Number(data.estadisticas?.minimo ?? sensor.valor_actual);
		estadisticas.maximo = Number(data.estadisticas?.maximo ?? sensor.valor_actual);
		estadisticas.promedio = Number(data.estadisticas?.promedio ?? sensor.valor_actual);
		estadisticas.total_muestras = Number(data.estadisticas?.total_muestras ?? 0);

		formOffset = sensor.offset;
		formRangoMax = sensor.rango_max;
		formFrecuencia = sensor.frecuencia_muestreo_hz;
	});

	// Buffer de alta frecuencia desacoplado ($state.raw) para rendimiento óptimo de LayerChart
	let bufferPuntos = $state.raw([]);
	let contadorMuestras = $state(0);
	let sseConectado = $state(false);

	// Porcentaje derivado respecto al límite
	const porcentaje = $derived(
		sensor.rango_max > 0
			? Math.min(100, Math.max(0, (sensor.valor_actual / sensor.rango_max) * 100))
			: 0
	);

	const anomalia = $derived(sensor.valor_actual > sensor.rango_max);

	// Cargar valores actualizados tras Form Action exitosa
	$effect(() => {
		if (form?.success && form.sensorActualizado) {
			sensor.offset = Number(form.sensorActualizado.offset);
			sensor.rango_max = Number(form.sensorActualizado.rango_max);
			sensor.frecuencia_muestreo_hz = Number(form.sensorActualizado.frecuencia_muestreo_hz);
			formOffset = sensor.offset;
			formRangoMax = sensor.rango_max;
			formFrecuencia = sensor.frecuencia_muestreo_hz;
			mensajeFeedback = { tipo: 'success', texto: form.mensaje };
		} else if (form?.success === false) {
			mensajeFeedback = { tipo: 'danger', texto: form.mensaje || 'Error al calibrar sensor' };
		}
	});

	// Función auxiliar para registrar muestras en el buffer inmutable $state.raw
	function registrarPuntoEnBuffer(nuevoValor) {
		contadorMuestras++;
		const num = Number(nuevoValor);

		// Actualizar estadísticas dinámicas en cliente
		if (estadisticas.total_muestras === 0 || num < estadisticas.minimo) estadisticas.minimo = num;
		if (estadisticas.total_muestras === 0 || num > estadisticas.maximo) estadisticas.maximo = num;
		estadisticas.promedio = Number(((estadisticas.promedio * 0.95) + (num * 0.05)).toFixed(1));
		estadisticas.total_muestras++;

		const nuevoPunto = { t: contadorMuestras, v: num };
		const maxPuntos = 40;

		const nuevoBuffer =
			bufferPuntos.length >= maxPuntos
				? [...bufferPuntos.slice(1), nuevoPunto]
				: [...bufferPuntos, nuevoPunto];

		bufferPuntos = nuevoBuffer;
	}

	// Inicialización del buffer desde data.historial de FastAPI y suscripción a SSE de telemetría
	$effect(() => {
		if (!data.fastapiOnline || !data.sensor) {
			bufferPuntos = [];
			contadorMuestras = 0;
			sseConectado = false;
			return;
		}

		const sensorId = sensor.id;
		// Cargar el historial real proveniente de FastAPI como estado inicial
		const historialReal = (data.historial || []).map((h, idx) => ({
			t: idx + 1,
			v: Number(h.valor)
		}));

		bufferPuntos = historialReal;
		contadorMuestras = historialReal.length;

		let eventSource = null;
		try {
			eventSource = new EventSource(`${FASTAPI_BASE_URL}/api/scada/stream`);

			eventSource.onopen = () => {
				sseConectado = true;
			};

			eventSource.onmessage = (e) => {
				try {
					const payload = JSON.parse(e.data);
					if (payload.sensores && Array.isArray(payload.sensores)) {
						const lectura = payload.sensores.find((s) => s.id === sensorId);
						if (lectura) {
							sensor.valor_actual = Number(lectura.valor_actual);
							registrarPuntoEnBuffer(lectura.valor_actual);
						}
					}
				} catch {}
			};

			eventSource.onerror = () => {
				sseConectado = false;
			};
		} catch {
			sseConectado = false;
		}

		return () => {
			if (eventSource) {
				eventSource.close();
			}
		};
	});

	const codigoServerDinamico = `// src/routes/proyecto-4-scada/sensores/[id]/+page.server.js
export async function load({ params, fetch }) {
    const res = await fetch(\`\${FASTAPI_BASE_URL}/api/sensores/\${params.id}\`);
    if (res.status === 404) throw error(404, 'Transductor no encontrado');
    const json = await res.json();
    return { sensor: json.sensor, estadisticas: json.estadisticas };
}

export const actions = {
    calibrar: async ({ params, request, fetch }) => {
        const formData = await request.formData();
        const offset = parseFloat(formData.get('offset'));
        const rango_max = parseFloat(formData.get('rango_max'));
        const res = await fetch(\`\${FASTAPI_BASE_URL}/api/sensores/\${params.id}/calibrar\`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ offset, rango_max })
        });
        return { success: res.ok, mensaje: 'Calibración guardada en EEPROM' };
    }
};`;

	const codigoLayerChartRaw = `// Vista Dinámica: Buffer de telemetría con $state.raw en Svelte 5
let bufferPuntos = $state.raw([]); // Sin reactividad profunda por elemento

function registrarMuestra(valor) {
    const nuevo = { t: ++contador, v: valor };
    // Asignación inmutable disparando un único ciclo de repintado a 60 fps
    bufferPuntos = bufferPuntos.length >= 40 
        ? [...bufferPuntos.slice(1), nuevo] 
        : [...bufferPuntos, nuevo];
}

<Chart data={bufferPuntos} x="t" y="v" xScale={scaleLinear()} yScale={scaleLinear()}>
    <Svg>
        <Axis placement="left" grid />
        <Area class="fill-blue-500/20" />
        <Spline class="stroke-blue-600" />
        <Rule y={sensor.rango_max} style="stroke: #ef4444; stroke-dasharray: 4,4;" />
    </Svg>
</Chart>`;
</script>

<svelte:head>
	<title>Nodo {sensor.id}: {sensor.nombre} — Calibración SCADA</title>
</svelte:head>

<!-- Migas de Pan (Breadcrumbs) y Volver al SCADA General -->
<nav class="breadcrumb has-arrow-separator mb-4" aria-label="breadcrumbs">
	<ul>
		<li><a href="/"><i class="fa-solid fa-compass mr-1"></i> Portal</a></li>
		<li><a href="/proyecto-4-scada"><i class="fa-solid fa-industry mr-1"></i> SCADA General</a></li>
		<li class="is-active">
			<a href="/proyecto-4-scada/sensores/{sensor.id}" class="has-text-weight-bold">
				<i class="fa-solid fa-microchip mr-1"></i> {sensor.id} ({sensor.modelo})
			</a>
		</li>
	</ul>
</nav>

{#if !data.fastapiOnline}
	<!-- Panel de Bloqueo Industrial SCADA si FastAPI no responde -->
	<div class="notification is-danger is-light p-6 mb-5 has-text-centered" style="border: 2px solid #dc2626; border-radius: 12px;">
		<span class="icon is-large has-text-danger mb-3">
			<i class="fa-solid fa-triangle-exclamation fa-3x"></i>
		</span>
		<h2 class="title is-4 has-text-danger-dark mb-2">
			SISTEMA DE CALIBRACIÓN BLOQUEADO: FASTAPI FUERA DE LÍNEA
		</h2>
		<p class="subtitle is-6 has-text-grey-dark mb-4">
			No es posible adquirir telemetría ni calibrar el transductor <strong>{data.sensorId}</strong> sin conexión activa con el servidor industrial.
		</p>
		<div class="box has-text-left p-4 mx-auto mb-4" style="max-width: 650px; background: #0f172a; color: #f8fafc; font-family: monospace; border-radius: 8px;">
			<p class="mb-2"><strong class="has-text-warning">Endpoints requeridos para calibración y telemetría:</strong></p>
			<p class="mb-1"><i class="fa-solid fa-arrow-right mr-2 has-text-info"></i>GET {FASTAPI_BASE_URL}/api/sensores/{data.sensorId} <span class="tag is-dark is-small ml-2">Ficha técnica</span></p>
			<p class="mb-1"><i class="fa-solid fa-arrow-right mr-2 has-text-info"></i>GET {FASTAPI_BASE_URL}/api/sensores <span class="tag is-dark is-small ml-2">Catálogo de nodos</span></p>
			<p class="mb-1"><i class="fa-solid fa-arrow-right mr-2 has-text-success"></i>GET {FASTAPI_BASE_URL}/api/scada/stream <span class="tag is-dark is-small ml-2">Telemetría SSE</span></p>
			<p class="mb-2"><i class="fa-solid fa-arrow-right mr-2 has-text-warning"></i>POST {FASTAPI_BASE_URL}/api/sensores/{data.sensorId}/calibrar <span class="tag is-dark is-small ml-2">Mando EEPROM</span></p>
			<p class="is-size-7 has-text-grey-light mb-1">Para restaurar la conexión, inicie el backend ejecutando:</p>
			<p class="tag is-black is-family-code p-2 w-100" style="display:block; text-align:left;">
				python backend_fastapi/main.py
			</p>
		</div>
		<div class="buttons is-centered">
			<button class="button is-danger has-text-weight-bold" onclick={() => location.reload()}>
				<i class="fa-solid fa-rotate mr-2"></i> Reintentar Conexión
			</button>
			<a href="/proyecto-4-scada" class="button is-light">
				<i class="fa-solid fa-arrow-left mr-2"></i> Volver al SCADA General
			</a>
		</div>
	</div>
{:else}
<!-- Encabezado del Transductor -->
<div class="level is-mobile mb-4" style="flex-wrap: wrap; gap: 0.5rem;">
	<div class="level-left">
		<div>
			<div class="is-flex is-align-items-center mb-1" style="gap: 0.5rem; flex-wrap: wrap;">
				<span class="tag is-dark is-medium is-family-code has-text-weight-bold">
					{sensor.id}
				</span>
				<span class="tag is-info is-light is-medium">
					<i class="fa-solid fa-microchip mr-1"></i> {sensor.nodo}
				</span>
				<span class="tag is-primary is-light is-medium">
					Modelo: {sensor.modelo}
				</span>
				{#if anomalia}
					<span class="tag is-danger has-text-weight-bold pulse-alerta">
						<i class="fa-solid fa-triangle-exclamation mr-1"></i> UMBRAL CRÍTICO EXCEDIDO
					</span>
				{:else}
					<span class="tag is-success is-light has-text-weight-semibold">
						<i class="fa-solid fa-circle-check mr-1"></i> RANGO NORMAL
					</span>
				{/if}
			</div>
			<h1 class="title is-3 mb-1">{sensor.nombre}</h1>
			<p class="is-size-6 has-text-grey">{sensor.descripcion}</p>
		</div>
	</div>

	<div class="level-right">
		<a href="/proyecto-4-scada" class="button is-light has-text-weight-semibold">
			<i class="fa-solid fa-arrow-left mr-2"></i> Volver al SCADA General
		</a>
	</div>
</div>

<!-- Selector Rápido de Nodos Industriales (Tabs) -->
{#if data.sensoresDisponibles && data.sensoresDisponibles.length > 0}
	<div class="tabs is-boxed mb-5">
		<ul>
			{#each data.sensoresDisponibles as item (item.id)}
				<li class={item.id === sensor.id ? 'is-active' : ''}>
					<a href="/proyecto-4-scada/sensores/{item.id}" class="has-text-weight-bold">
						<span class="tag {item.id === sensor.id ? 'is-link' : 'is-light'} is-small mr-2 is-family-code">
							{item.id}
						</span>
						<span>{(item.nombre || item.id).split(' ')[0]} ({item.unidad})</span>
					</a>
				</li>
			{/each}
		</ul>
	</div>
{/if}

<!-- 4 Métricas y Estadísticas Calculadas por el Servidor -->
<div class="columns is-multiline mb-5">
	<div class="column is-6-tablet is-3-desktop">
		<div class="box metric-card" style="border-top: 4px solid #2563eb;">
			<p class="heading has-text-grey">Lectura en Tiempo Real</p>
			<p class="title is-3 is-family-code mb-1 {anomalia ? 'has-text-danger' : 'has-text-link'}">
				{sensor.valor_actual.toFixed(1)} <span class="is-size-5 has-text-grey">{sensor.unidad}</span>
			</p>
			<p class="is-size-7 has-text-grey">
				Offset aplicado: <strong>{sensor.offset >= 0 ? '+' : ''}{sensor.offset.toFixed(2)} {sensor.unidad}</strong>
			</p>
		</div>
	</div>

	<div class="column is-6-tablet is-3-desktop">
		<div class="box metric-card" style="border-top: 4px solid #10b981;">
			<p class="heading has-text-grey">Mínimo Registrado</p>
			<p class="title is-3 is-family-code mb-1 has-text-success-dark">
				{estadisticas.minimo.toFixed(1)} <span class="is-size-5 has-text-grey">{sensor.unidad}</span>
			</p>
			<p class="is-size-7 has-text-grey">Cota inferior observada en proceso</p>
		</div>
	</div>

	<div class="column is-6-tablet is-3-desktop">
		<div class="box metric-card" style="border-top: 4px solid #f59e0b;">
			<p class="heading has-text-grey">Promedio del Lazo</p>
			<p class="title is-3 is-family-code mb-1 has-text-warning-dark">
				{estadisticas.promedio.toFixed(1)} <span class="is-size-5 has-text-grey">{sensor.unidad}</span>
			</p>
			<p class="is-size-7 has-text-grey">Media móvil exponencial de planta</p>
		</div>
	</div>

	<div class="column is-6-tablet is-3-desktop">
		<div class="box metric-card" style="border-top: 4px solid #dc2626;">
			<p class="heading has-text-grey">Máximo Registrado</p>
			<p class="title is-3 is-family-code mb-1 has-text-danger">
				{estadisticas.maximo.toFixed(1)} <span class="is-size-5 has-text-grey">{sensor.unidad}</span>
			</p>
			<p class="is-size-7 has-text-grey">
				Límite de Alarma: <strong>{sensor.rango_max} {sensor.unidad}</strong>
			</p>
		</div>
	</div>
</div>

<!-- Gráfica de Telemetría en Vivo (LayerChart) y Panel de Calibración -->
<div class="columns is-multiline mb-6">
	<!-- Gráfica LayerChart con Rule y Spline -->
	<div class="column is-12-tablet is-8-desktop">
		<div class="card p-4" style="border-radius: 10px; height: 100%;">
			<div class="level is-mobile mb-3">
				<div class="level-left">
					<h3 class="title is-5 mb-0">
						<i class="fa-solid fa-chart-line mr-2 has-text-link"></i>
						Telemetría Continua (Buffer $state.raw a 60 fps)
					</h3>
				</div>
				<div class="level-right">
					<span class="tag is-white" style="border: 1px solid #cbd5e1;">
						<i class="fa-solid fa-satellite-dish mr-1 {sseConectado ? 'has-text-success' : 'has-text-danger'}"></i>
						{sseConectado ? `FastAPI SSE (${FASTAPI_BASE_URL}/api/scada/stream)` : 'SSE Desconectado'}
					</span>
				</div>
			</div>

			<!-- Leyenda Metrológica -->
			<div class="tags mb-3">
				<span class="tag is-light is-size-7">
					<span class="legend-box mr-1" style="background:#2563eb;"></span>
					Curva de Lectura ({sensor.unidad})
				</span>
				<span class="tag is-danger is-light is-size-7">
					<span class="legend-box mr-1" style="background:#ef4444; border-top: 2px dashed #ef4444;"></span>
					Umbral Crítico (Rule en y = {sensor.rango_max} {sensor.unidad})
				</span>
				<span class="tag is-white is-size-7 ml-auto" style="border:1px solid #e2e8f0;">
					Ventana: 40 muestras circulares
				</span>
			</div>

			<!-- Canvas del Gráfico LayerChart -->
			<div class="chart-container" style="height: 320px; width: 100%; position: relative;">
				{#if bufferPuntos.length > 0}
					<Chart
						data={bufferPuntos}
						x="t"
						y="v"
						xScale={scaleLinear()}
						yScale={scaleLinear()}
						yDomain={[0, Math.max(sensor.rango_max * 1.3, estadisticas.maximo * 1.15, 10)]}
						padding={{ top: 20, right: 20, bottom: 30, left: 45 }}
					>
						<Svg>
							<Axis placement="left" grid rule format={(d) => `${d} ${sensor.unidad}`} />
							<Axis placement="bottom" rule />
							<Area style="fill: rgba(37, 99, 235, 0.15);" />
							<Spline style="stroke: #2563eb; stroke-width: 2.5px;" />
							<Rule
								y={sensor.rango_max}
								style="stroke: #ef4444; stroke-width: 2px; stroke-dasharray: 4,4;"
							/>
						</Svg>
					</Chart>
				{/if}
			</div>

			<p class="is-size-7 has-text-grey mt-2">
				<i class="fa-solid fa-lightbulb mr-1 has-text-warning"></i>
				La línea roja horizontal es renderizada mediante el componente <code>&lt;Rule y={'{'}sensor.rango_max{'}'} /&gt;</code> de LayerChart.
				Si modificas el <em>Rango Máximo</em> en el panel lateral, la regla de umbral se desplazará reactivamente sin perder el histórico.
			</p>
		</div>
	</div>

	<!-- Panel de Calibración Remota con use:enhance -->
	<div class="column is-12-tablet is-4-desktop">
		<div class="card p-4" style="border-radius: 10px; height: 100%; border: 1px solid #cbd5e1;">
			<div class="is-flex is-align-items-center mb-3">
				<span class="tag is-primary is-medium mr-2">
					<i class="fa-solid fa-sliders"></i>
				</span>
				<div>
					<h3 class="title is-5 mb-0">Calibración Remota</h3>
					<p class="is-size-7 has-text-grey">Parámetros del transductor en EEPROM</p>
				</div>
			</div>

			{#if mensajeFeedback}
				<div class="notification is-{mensajeFeedback.tipo} is-light p-3 mb-3 is-size-7" style="border-left: 4px solid;">
					<button
						type="button"
						class="delete is-small"
						onclick={() => (mensajeFeedback = null)}
						aria-label="Cerrar notificación"
					></button>
					<strong>{mensajeFeedback.tipo === 'success' ? '¡Éxito!' : 'Aviso:'}</strong>
					{mensajeFeedback.texto}
				</div>
			{/if}

			<form
				method="POST"
				action="?/calibrar"
				use:enhance={() => {
					guardando = true;
					mensajeFeedback = null;
					return async ({ update }) => {
						await update();
						guardando = false;
					};
				}}
			>
				<!-- Offset de Cero -->
				<div class="field mb-3">
					<label class="label is-small" for="calib-offset">
						Offset de Calibración ({sensor.unidad})
						<span class="has-text-grey has-text-weight-normal is-size-7">(Compensa deriva física)</span>
					</label>
					<div class="control has-icons-left">
						<input
							id="calib-offset"
							name="offset"
							class="input is-small is-family-code"
							type="number"
							step="0.05"
							bind:value={formOffset}
							required
						/>
						<span class="icon is-small is-left">
							<i class="fa-solid fa-plus-minus"></i>
						</span>
					</div>
					<p class="help is-size-7">Se suma algebraicamente a la lectura bruta del ADC/I2C.</p>
				</div>

				<!-- Límite Superior de Alarma (Rango Máximo) -->
				<div class="field mb-3">
					<label class="label is-small" for="calib-rango">
						Límite Superior de Alarma / Rango Máx ({sensor.unidad})
					</label>
					<div class="control has-icons-left">
						<input
							id="calib-rango"
							name="rango_max"
							class="input is-small is-family-code"
							type="number"
							step="0.5"
							min="1"
							bind:value={formRangoMax}
							required
						/>
						<span class="icon is-small is-left">
							<i class="fa-solid fa-bell"></i>
						</span>
					</div>
					<p class="help is-size-7">Mueve el umbral <code>&lt;Rule /&gt;</code> en la gráfica SCADA.</p>
				</div>

				<!-- Frecuencia de Muestreo del Microcontrolador -->
				<div class="field mb-4">
					<label class="label is-small" for="calib-freq">
						Tasa de Muestreo del Microcontrolador (Hz)
					</label>
					<div class="control has-icons-left">
						<div class="select is-small is-fullwidth">
							<select id="calib-freq" name="frecuencia_muestreo_hz" bind:value={formFrecuencia}>
								<option value={1}>1 Hz (Baja Potencia / Temperatura)</option>
								<option value={5}>5 Hz (Monitoreo Térmico Estándar)</option>
								<option value={10}>10 Hz (Procesos Industriales Típicos)</option>
								<option value={20}>20 Hz (Dinámica de Presión)</option>
								<option value={50}>50 Hz (Vibraciones y Acelerómetros)</option>
								<option value={100}>100 Hz (Transitorios Rápidos)</option>
							</select>
						</div>
						<span class="icon is-small is-left">
							<i class="fa-solid fa-wave-square"></i>
						</span>
					</div>
					<p class="help is-size-7">Configura el temporizador de interrupción por hardware del ESP32/STM32.</p>
				</div>

				<div class="field mt-4">
					<button
						type="submit"
						class="button is-link is-fullwidth has-text-weight-bold {guardando ? 'is-loading' : ''}"
					>
						<i class="fa-solid fa-floppy-disk mr-2"></i> Grabar en EEPROM del Nodo
					</button>
				</div>
			</form>

			<hr class="my-3" />

			<div class="is-size-7 has-text-grey">
				<p class="mb-1">
					<strong><i class="fa-solid fa-shield mr-1"></i> Form Actions + use:enhance:</strong>
				</p>
				<p>
					El formulario procesa la calibración sin recargar la pantalla completa, preservando intacto
					el buffer histórico de LayerChart y el hilo de telemetría SSE.
				</p>
			</div>
		</div>
	</div>
</div>
{/if}

<!-- Visor Pedagógico de Código -->
<CodeViewer
	titulo="Código Fuente — Ruta Dinámica y Calibración Remota"
	archivos={[
		{
			nombre: '+page.server.js (Ruta Dinámica y Calibración)',
			descripcion: 'Carga metadatos del transductor /sensores/[id] y procesa la Form Action de calibración EEPROM.',
			codigo: codigoServerDinamico
		},
		{
			nombre: '+page.svelte (LayerChart + $state.raw)',
			descripcion: 'Buffer inmutable superficial ($state.raw) que evita sobrecarga reactiva a 60 fps con <Rule y={rango_max} />.',
			codigo: codigoLayerChartRaw
		}
	]}
/>

<style>
	.metric-card {
		border-radius: 10px;
		background: #ffffff;
		border: 1px solid #cbd5e1;
		transition: transform 0.15s ease;
	}
	.metric-card:hover {
		transform: translateY(-2px);
	}

	.legend-box {
		display: inline-block;
		width: 12px;
		height: 12px;
		border-radius: 2px;
		vertical-align: middle;
	}

	@keyframes pulse-alerta-anim {
		0%, 100% { opacity: 1; }
		50% { opacity: 0.65; }
	}

	.pulse-alerta {
		animation: pulse-alerta-anim 1s infinite;
	}
</style>
