<script>
	/**
	 * Proyecto 4: El Dashboard SCADA Completo
	 * Arquitectura BFF (Backend-For-Frontend) en SvelteKit + Telemetría SSE + Svelte 5 Runes
	 *
	 * Cátedra: Lenguajes de Programación Visual — FIUNA
	 */
	import { FASTAPI_BASE_URL } from '$lib/config.js';
	import { autoScroll } from '$lib/actions/autoScroll.js';
	import SensorCard from '$lib/components/SensorCard.svelte';
	import EmergencyStopModal from '$lib/components/EmergencyStopModal.svelte';
	import CodeViewer from '$lib/components/CodeViewer.svelte';

	let { data, form } = $props();

	// Estado reactivo inicializado exclusivamente con el snapshot SSR de Node desde FastAPI
	let sensores = $state(data.sensoresIniciales || []);
	let eventos = $state(data.eventosIniciales || []);
	let estadoPlanta = $state(data.estadoPlanta || (data.fastapiOnline ? 'EN_MARCHA' : 'DESCONECTADO'));

	$effect(() => {
		sensores = data.sensoresIniciales || [];
		eventos = data.eventosIniciales || [];
		estadoPlanta = data.estadoPlanta || (data.fastapiOnline ? 'EN_MARCHA' : 'DESCONECTADO');
	});

	let autoScrollActivo = $state(true);
	let sseConectado = $state(false);
	let paquetesRecibidos = $state(0);
	let ultimaHoraStream = $state('--:--:--');

	// Reacción ante las Form Actions (Paro o Restauración)
	$effect(() => {
		if (form?.success) {
			if (form.accion === 'PARAR') {
				estadoPlanta = 'PARO_EMERGENCIA';
				eventos = [
					...eventos,
					{
						timestamp: new Date().toLocaleTimeString(),
						nivel: 'CRITICAL',
						origen: 'SCADA-Web',
						mensaje: `Solicitud de Paro ejecutada con éxito. RTT de red: ${form.latenciaRttMs} ms`
					}
				];
			} else if (form.accion === 'RESTAURAR') {
				estadoPlanta = 'EN_MARCHA';
				eventos = [
					...eventos,
					{
						timestamp: new Date().toLocaleTimeString(),
						nivel: 'INFO',
						origen: 'SCADA-Web',
						mensaje: `Planta rearmada administrativamente. RTT de red: ${form.latenciaRttMs} ms`
					}
				];
			}
		}
	});

	// Conexión reactiva al stream SSE de FastAPI con limpieza automática
	$effect(() => {
		if (!data.fastapiOnline) {
			sseConectado = false;
			return;
		}

		let eventSource = null;
		try {
			eventSource = new EventSource(`${FASTAPI_BASE_URL}/api/scada/stream`);

			eventSource.onopen = () => {
				sseConectado = true;
				eventos = [
					...eventos,
					{
						timestamp: new Date().toLocaleTimeString(),
						nivel: 'INFO',
						origen: 'SSE-Client',
						mensaje: `Canal SSE establecido con ${FASTAPI_BASE_URL}/api/scada/stream (250 ms)`
					}
				];
			};

			eventSource.onmessage = (e) => {
				try {
					const datos = JSON.parse(e.data);
					if (datos.sensores && Array.isArray(datos.sensores)) {
						sensores = datos.sensores;
					}
					if (datos.estado_planta) {
						estadoPlanta = datos.estado_planta;
					}
					// Procesar último evento recibido de FastAPI evitando duplicados por id o timestamp/mensaje
					if (datos.ultimo_evento) {
						const ev = datos.ultimo_evento;
						const yaExiste =
							eventos.length > 0 &&
							((ev.id && eventos[eventos.length - 1].id === ev.id) ||
								(eventos[eventos.length - 1].timestamp === ev.timestamp &&
									eventos[eventos.length - 1].mensaje === ev.mensaje));
						if (!yaExiste) {
							eventos = [...eventos, ev];
						}
					}
					paquetesRecibidos++;
					ultimaHoraStream = new Date().toLocaleTimeString();
				} catch (err) {
					console.error('Error al procesar mensaje SSE SCADA:', err);
				}
			};

			eventSource.onerror = () => {
				sseConectado = false;
			};
		} catch (err) {
			sseConectado = false;
		}

		return () => {
			if (eventSource) {
				eventSource.close();
			}
		};
	});

	function limpiarConsola() {
		eventos = [];
	}

	const codigoBFF = `// src/routes/proyecto-4-scada/+page.server.js
import { FASTAPI_BASE_URL } from '$lib/config.js';

export async function load({ fetch }) {
    try {
        const res = await fetch(\`\${FASTAPI_BASE_URL}/api/sensores\`);
        const json = await res.json();
        return {
            fastapiOnline: true,
            estadoPlanta: json.estado_planta,
            sensoresIniciales: json.sensores,
            eventosIniciales: json.eventos_recientes
        };
    } catch {
        return { fastapiOnline: false, estadoPlanta: 'DESCONECTADO', sensoresIniciales: [] };
    }
}

export const actions = {
    paroEmergencia: async ({ request, fetch }) => {
        const t0 = performance.now();
        const res = await fetch(\`\${FASTAPI_BASE_URL}/api/planta/paro-emergencia\`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ accion: 'PARAR' })
        });
        const latenciaRttMs = Math.round(performance.now() - t0);
        return { success: res.ok, accion: 'PARAR', latenciaRttMs };
    }
};`;

	const codigoSensorCard = `<!-- src/lib/components/SensorCard.svelte -->
<scr` + `ipt>
    let { sensor, estadoPlanta = 'EN_MARCHA', alertaSnippet } = $props();

    const porcentaje = $derived(
        sensor.rango_max > 0 ? (sensor.valor_actual / sensor.rango_max) * 100 : 0
    );
    const anomalia = $derived(sensor.valor_actual > sensor.rango_max);
</scr` + `ipt>

<div class="card {anomalia ? 'anomalia-activa' : ''}">
    <span class="tag is-dark">{sensor.id}</span>
    <p class="valor">{sensor.valor_actual} {sensor.unidad}</p>
    <progress value={porcentaje} max="100" />
    {#if anomalia && alertaSnippet}
        {@render alertaSnippet(sensor)}
    {/if}
</div>`;

	const codigoAutoScroll = `// src/lib/actions/autoScroll.js
export function autoScroll(node, enabled = true) {
    let activo = enabled;
    const scrollAlFinal = () => {
        if (activo && node) node.scrollTop = node.scrollHeight;
    };
    const observer = new MutationObserver(() => scrollAlFinal());
    observer.observe(node, { childList: true, subtree: true });
    return {
        update(nuevoEstado) {
            activo = Boolean(nuevoEstado);
            if (activo) scrollAlFinal();
        },
        destroy() { observer.disconnect(); }
    };
}`;
</script>

<svelte:head>
	<title>Proyecto 4: Dashboard SCADA Completo (BFF + Runes) — FIUNA</title>
</svelte:head>

<!-- Título y Encabezado del Proyecto -->
<div class="mb-5">
	<div class="level is-mobile mb-2">
		<div class="level-left">
			<span class="tag is-success is-medium has-text-weight-bold">
				<i class="fa-solid fa-industry mr-2"></i> PROYECTO 04
			</span>
			<span class="tag is-dark ml-2 is-hidden-mobile is-family-code">
				BFF + Svelte 5 Runes + SSE + Bits UI
			</span>
		</div>
		<div class="level-right">
			<div class="tags has-addons mb-0">
				<span class="tag is-dark">Estado Planta:</span>
				{#if estadoPlanta === 'EN_MARCHA'}
					<span class="tag is-success has-text-weight-bold">
						<i class="fa-solid fa-circle-play mr-1"></i> EN MARCHA
					</span>
				{:else if estadoPlanta === 'PARO_EMERGENCIA'}
					<span class="tag is-danger has-text-weight-bold">
						<i class="fa-solid fa-ban mr-1"></i> PARO DE EMERGENCIA
					</span>
				{:else}
					<span class="tag is-warning has-text-weight-bold">
						<i class="fa-solid fa-circle-question mr-1"></i> {estadoPlanta}
					</span>
				{/if}
			</div>
		</div>
	</div>

	<h1 class="title is-2 mb-2">El Dashboard SCADA Completo</h1>
	<p class="subtitle is-6 has-text-grey mb-4">
		Integración integral de la pirámide de supervisión industrial: arquitectura <strong>Backend-For-Frontend (BFF)</strong>
		en el servidor SvelteKit, hidratación de telemetría a <strong>250 ms por Server-Sent Events</strong>,
		vistas dinámicas de nodo y <strong>Paro de Planta</strong> con medición de latencia RTT.
	</p>

	<!-- Fila de Estado de Canales de Comunicación -->
	<div class="box p-3 mb-4" style="background:#f8fafc; border:1px solid #cbd5e1;">
		<div class="level is-mobile mb-0" style="flex-wrap: wrap; gap: 0.5rem;">
			<div class="level-left" style="gap: 0.5rem; flex-wrap: wrap;">
				<span class="tag is-white" style="border: 1px solid #cbd5e1;">
					<i class="fa-solid fa-server mr-1 has-text-link"></i>
					<strong>BFF SSR Node:</strong>&nbsp;<span class="has-text-success has-text-weight-bold">SIN CORS</span>
				</span>
				<span class="tag is-white" style="border: 1px solid #cbd5e1;">
					<i class="fa-solid fa-bolt mr-1 has-text-warning"></i>
					<strong>Canal SSE Telemetría:</strong>&nbsp;
					{#if sseConectado}
						<span class="has-text-success has-text-weight-bold">STREAM ACTIVO</span>
					{:else if !data.fastapiOnline}
						<span class="has-text-danger has-text-weight-bold">DESCONECTADO (FASTAPI OFFLINE)</span>
					{:else}
						<span class="has-text-warning has-text-weight-bold">CONECTANDO A FASTAPI...</span>
					{/if}
				</span>
				<span class="tag is-white" style="border: 1px solid #cbd5e1;">
					<i class="fa-solid fa-box-archive mr-1 has-text-primary"></i>
					<strong>Paquetes:</strong>&nbsp;<span class="is-family-code">{paquetesRecibidos}</span>
				</span>
				<span class="tag is-white" style="border: 1px solid #cbd5e1;">
					<i class="fa-solid fa-clock mr-1 has-text-grey"></i>
					<strong>Última Muestra:</strong>&nbsp;<span class="is-family-code">{ultimaHoraStream}</span>
				</span>
			</div>

			<div class="level-right">
				<span class="tag is-dark is-family-code is-size-7">
					FastAPI: {FASTAPI_BASE_URL}
				</span>
			</div>
		</div>
	</div>
</div>

<!-- Modal y Disparador de Paro de Emergencia Administrativo -->
<EmergencyStopModal
	{estadoPlanta}
	latenciaRttMs={form?.latenciaRttMs ?? null}
	ultimoEvento={eventos[eventos.length - 1]}
/>

<!-- Snippet de Alerta Crítica (Svelte 5 Runes) -->
{#snippet alertaCritica(sensor)}
	<div
		class="notification is-danger is-light p-2 mb-0 is-size-7"
		style="border-left: 4px solid #dc2626; border-radius: 6px;"
	>
		<div class="is-flex is-align-items-center">
			<i class="fa-solid fa-triangle-exclamation mr-2 has-text-danger is-size-5"></i>
			<div>
				<strong class="has-text-danger-dark">DISPARO DE ALARMA METROLÓGICA</strong><br />
				La lectura ({sensor.valor_actual} {sensor.unidad}) supera el límite de seguridad ({sensor.rango_max} {sensor.unidad}).
			</div>
		</div>
	</div>
{/snippet}

{#if !data.fastapiOnline}
	<!-- Panel de Bloqueo Industrial SCADA si FastAPI no responde -->
	<div class="notification is-danger is-light p-6 mb-5 has-text-centered" style="border: 2px solid #dc2626; border-radius: 12px;">
		<span class="icon is-large has-text-danger mb-3">
			<i class="fa-solid fa-triangle-exclamation fa-3x"></i>
		</span>
		<h2 class="title is-4 has-text-danger-dark mb-2">
			SISTEMA SCADA BLOQUEADO: SERVIDOR FASTAPI FUERA DE LÍNEA
		</h2>
		<p class="subtitle is-6 has-text-grey-dark mb-4">
			El centro de supervisión industrial opera <strong>100% en tiempo real</strong> y prohíbe el uso de datos simulados locales.
		</p>
		<div class="box has-text-left p-4 mx-auto mb-4" style="max-width: 650px; background: #0f172a; color: #f8fafc; font-family: monospace; border-radius: 8px;">
			<p class="mb-2"><strong class="has-text-warning">Endpoints requeridos para supervisión activa:</strong></p>
			<p class="mb-1"><i class="fa-solid fa-arrow-right mr-2 has-text-info"></i>GET {FASTAPI_BASE_URL}/api/sensores <span class="tag is-dark is-small ml-2">Snapshot inicial BFF</span></p>
			<p class="mb-2"><i class="fa-solid fa-arrow-right mr-2 has-text-success"></i>GET {FASTAPI_BASE_URL}/api/scada/stream <span class="tag is-dark is-small ml-2">Telemetría 250ms SSE</span></p>
			<p class="is-size-7 has-text-grey-light mb-1">Para restaurar la conexión, inicie el backend ejecutando:</p>
			<p class="tag is-black is-family-code p-2 w-100" style="display:block; text-align:left;">
				python backend_fastapi/main.py
			</p>
		</div>
		<button class="button is-danger has-text-weight-bold" onclick={() => location.reload()}>
			<i class="fa-solid fa-rotate mr-2"></i> Reintentar Conexión con Planta
		</button>
	</div>
{:else}
	<!-- Matriz de Transductores de Planta (SensorCard + Snippet) -->
	<div class="mb-5">
		<div class="level is-mobile mb-3">
			<div class="level-left">
				<h2 class="title is-4 mb-0">
					<i class="fa-solid fa-network-wired mr-2 has-text-link"></i>
					Transductores del Proceso en Vivo
				</h2>
			</div>
			<div class="level-right">
				<span class="tag is-info is-light is-size-7">
					Recibiendo cada 250 ms &middot; {sensores.length} Nodos Activos
				</span>
			</div>
		</div>

		{#if sensores.length === 0}
			<div class="notification is-warning is-light p-4 has-text-centered">
				<i class="fa-solid fa-spinner fa-spin mr-2"></i> Adquiriendo telemetría de transductores...
			</div>
		{:else}
			<div class="columns is-multiline">
				{#each sensores as sensor (sensor.id)}
					<div class="column is-12-mobile is-6-tablet is-3-desktop">
						<SensorCard
							{sensor}
							{estadoPlanta}
							alertaSnippet={alertaCritica}
						/>
					</div>
				{/each}
			</div>
		{/if}
	</div>
{/if}

<!-- Consola de Diagnóstico Industrial con Acción Nativa use:autoScroll -->
<div class="card mb-6" style="border: 1px solid #0f172a; border-radius: 10px; overflow: hidden;">
	<header
		class="card-header px-4 py-3 is-justify-content-space-between is-align-items-center"
		style="background-color: #0f172a; color: #f8fafc;"
	>
		<div class="is-flex is-align-items-center" style="gap: 0.5rem;">
			<i class="fa-solid fa-terminal has-text-success"></i>
			<span class="has-text-weight-bold is-family-code is-size-6">
				CONSOLA DE DIAGNÓSTICO INDUSTRIAL (LOGS SCADA EN TIEMPO REAL)
			</span>
			<span class="tag is-dark is-size-7 ml-2">
				{eventos.length} registros
			</span>
		</div>

		<div class="buttons has-addons mb-0">
			<button
				type="button"
				class="button is-small {autoScrollActivo ? 'is-success' : 'is-warning'}"
				onclick={() => (autoScrollActivo = !autoScrollActivo)}
				title="Pausar o reanudar el desplazamiento automático al recibir nuevos eventos"
			>
				<i class="fa-solid {autoScrollActivo ? 'fa-pause' : 'fa-play'} mr-1"></i>
				{autoScrollActivo ? 'Auto-Scroll ACTIVO' : 'Auto-Scroll PAUSADO'}
			</button>
			<button
				type="button"
				class="button is-small is-dark"
				onclick={limpiarConsola}
				title="Limpiar buffer de eventos"
			>
				<i class="fa-solid fa-eraser mr-1"></i> Limpiar
			</button>
		</div>
	</header>

	<!-- Contenedor de Logs con la Acción Nativa use:autoScroll -->
	<div
		use:autoScroll={autoScrollActivo}
		class="console-body p-4"
		style="max-height: 260px; min-height: 180px; overflow-y: auto; background-color: #020617; font-family: 'JetBrains Mono', monospace;"
	>
		{#if eventos.length === 0}
			<p class="has-text-grey is-size-7">-- Buffer de diagnóstico vacío --</p>
		{:else}
			{#each eventos as ev, idx (idx)}
				<div class="console-line is-size-7 mb-1 is-flex is-align-items-flex-start">
					<span class="has-text-grey mr-2">[{ev.timestamp || '--:--:--'}]</span>

					{#if ev.nivel === 'CRITICAL'}
						<span class="tag is-danger is-small py-0 px-1 mr-2 has-text-weight-bold">CRIT</span>
					{:else if ev.nivel === 'WARNING'}
						<span class="tag is-warning is-small py-0 px-1 mr-2 has-text-weight-bold">WARN</span>
					{:else if ev.nivel === 'ACTION'}
						<span class="tag is-info is-small py-0 px-1 mr-2 has-text-weight-bold">ACTN</span>
					{:else}
						<span class="tag is-dark is-small py-0 px-1 mr-2">INFO</span>
					{/if}

					<span class="has-text-primary-light mr-2">&lt;{ev.origen || 'SCADA'}&gt;</span>
					<span class="has-text-white-bis" style="flex: 1 1 auto; word-break: break-word;">
						{ev.mensaje}
					</span>
				</div>
			{/each}
		{/if}
	</div>

	<footer class="p-2 px-4 is-size-7 has-text-grey" style="background:#0f172a; border-top:1px solid #1e293b;">
		<i class="fa-solid fa-info-circle mr-1 has-text-info"></i>
		Acción nativa de Svelte <code>use:autoScroll</code> acoplada a un <code>MutationObserver</code>.
		Pausa el scroll para congelar la lectura mientras continúan ingresando datos.
	</footer>
</div>

<!-- Fundamento Pedagógico de la Arquitectura de 3 Capas -->
<div class="card p-5 mb-5" style="border-left: 5px solid #10b981;">
	<h3 class="title is-5 mb-2">
		<i class="fa-solid fa-layer-group has-text-success mr-2"></i>
		Arquitectura SCADA de 3 Capas (Clase 7)
	</h3>
	<div class="content is-size-6">
		<p>
			Este proyecto materializa el desacoplamiento estricto requerido en mecatrónica moderna:
		</p>
		<ol>
			<li>
				<strong>Servidor Industrial FastAPI (Puerto :8000):</strong>
				Genera telemetría determinista a 4 Hz (250 ms), almacena buffers circulares y atiende endpoints REST de control.
			</li>
			<li>
				<strong>BFF SvelteKit (+page.server.js):</strong>
				Elimina problemas de CORS consultando al backend durante el SSR (Server-Side Rendering). Garantiza que la página abra instantáneamente con los valores vigentes sin esperar ciclos de JavaScript en el cliente.
			</li>
			<li>
				<strong>Cliente Reactivo Svelte 5 (+page.svelte):</strong>
				Toma el control en el navegador (hidratación), levanta la conexión <code>EventSource</code> para recibir deltas cada 250 ms, y gestiona interacciones seguras mediante Form Actions con <code>use:enhance</code>.
			</li>
		</ol>
	</div>
</div>

<!-- Visor Pedagógico de Código Fuente -->
<CodeViewer
	titulo="Código Fuente — Proyecto 4: SCADA Fullstack"
	archivos={[
		{
			nombre: '+page.server.js (BFF y Actions)',
			descripcion: 'Carga inicial SSR en Node sin CORS y Server Actions para Paro de Emergencia con medición de latencia RTT.',
			codigo: codigoBFF
		},
		{
			nombre: 'SensorCard.svelte (Runes y Snippets)',
			descripcion: 'Componente atómico que usa $props(), $derived() y renderiza {#snippet alertaSnippet(sensor)} ante anomalías.',
			codigo: codigoSensorCard
		},
		{
			nombre: 'autoScroll.js (Acción Nativa)',
			descripcion: 'Directiva use:autoScroll con MutationObserver que respeta si el operador pausó el scroll de la consola.',
			codigo: codigoAutoScroll
		}
	]}
/>

<style>
	.console-body::-webkit-scrollbar {
		width: 8px;
	}
	.console-body::-webkit-scrollbar-track {
		background: #020617;
	}
	.console-body::-webkit-scrollbar-thumb {
		background: #334155;
		border-radius: 4px;
	}
	.console-body::-webkit-scrollbar-thumb:hover {
		background: #475569;
	}
</style>
