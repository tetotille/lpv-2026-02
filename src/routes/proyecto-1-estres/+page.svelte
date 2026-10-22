<script>
	/**
	 * Proyecto 1: "El Banco de Estrés" (Límite Físico vs. Límite de Renderizado)
	 * Cátedra: Lenguajes de Programación Visual (LPV) - FIUNA
	 *
	 * Demostración experimental del desacoplamiento temporal entre la frecuencia
	 * de muestreo del sensor mecatrónico (100 - 1000 Hz) y el refresco visual (60 Hz).
	 *
	 * Implementado exclusivamente con Svelte 5 Runes ($state, $state.raw, $derived, $effect).
	 */

	import { Chart, Svg, Spline, Axis } from 'layerchart';
	import { scaleLinear } from 'd3-scale';

	import FpsMeter from '$lib/components/FpsMeter.svelte';
	import CodeViewer from '$lib/components/CodeViewer.svelte';
	import GeneradorWorker from '$lib/workers/generador_carga.worker.js?worker';

	// =========================================================================
	// ESTADO DE CONTROL DE ENSAYO
	// =========================================================================
	let workerActivo = $state(false);
	let frecuenciaSeleccionada = $state(100); // 100, 250, 500, 1000 Hz
	let modoSeleccionado = $state('B'); // 'A' (Fallo $state) | 'B' (Desacoplado $state.raw + rAF)

	// Contadores y telemetría de entrada
	let muestrasRecibidasPorSeg = $state(0);
	let contadorMuestrasSegundo = 0;
	let totalMuestrasAcumuladas = $state(0);
	let ultimaMuestra = $state({
		id: 0,
		timestamp: 0,
		tRelativo: 0,
		aceleracionG: 0,
		velocidadRpm: 1710,
		pasosEncoder: 0
	});

	// =========================================================================
	// MODO A: FALLO DE DISEÑO (Reactividad Profunda $state en alta frecuencia)
	// =========================================================================
	// Array reactivo profundo: en cada mensaje se hace unshift directo.
	let listaModoA = $state([]);

	// =========================================================================
	// MODO B: DESACOPLAMIENTO TEMPORAL ($state.raw + buffer plano + rAF a 60fps)
	// =========================================================================
	// 1. Buffer plano de JavaScript: NO reactivo, memoria pura O(1)
	let bufferCrudo = [];
	// 2. Estado visual inmutable: Solo notifica a Svelte cuando se reemplaza la referencia
	let serieModoB = $state.raw([]);

	// Estado visual del Rotor Mecatrónico animado (en grados 0 - 360°)
	let anguloRotor = $state(0);

	// Referencia al Web Worker
	let worker = null;

	// Inicialización del Worker y del Lazo de Animación en el cliente
	$effect(() => {
		if (typeof window === 'undefined') return;

		worker = new GeneradorWorker();

		worker.onmessage = (evento) => {
			const data = evento.data || {};
			if (data.tipo === 'MUESTRA' && data.payload) {
				const payload = data.payload;
				contadorMuestrasSegundo++;
				totalMuestrasAcumuladas++;
				ultimaMuestra = payload;

				if (modoSeleccionado === 'A') {
					// MODO A: Mutación directa sobre $state en cada muestra entrante
					// Provoca Layout Thrashing y saturación del Event Loop a 500-1000 Hz
					const hashCalculado = (
						(payload.id * 2654435761) %
						4294967296
					)
						.toString(16)
						.padStart(8, '0');

					listaModoA.unshift({
						...payload,
						hashCalculado
					});

					// Mantenemos 180 elementos en el DOM para evidenciar el costo de reconciliación
					if (listaModoA.length > 180) {
						listaModoA.pop();
					}
				} else {
					// MODO B: Inserción en memoria plana JS (cero sobrecosto de reactividad)
					bufferCrudo.push(payload);
					if (bufferCrudo.length > 400) {
						bufferCrudo.splice(0, bufferCrudo.length - 400);
					}
				}
			}
		};

		// Lazo de animación visual independiente sincronizado con la pantalla (60 Hz)
		let ultimoRafTime = performance.now();
		let animId;

		const loopVisual = (ahora) => {
			const dt = (ahora - ultimoRafTime) / 1000;
			ultimoRafTime = ahora;

			// Rotación continua del rotor (simula la rotación a velocidad del eje)
			// Si el hilo principal está saturado (Modo A), dt crece erráticamente y la aguja tartamudea
			anguloRotor = (anguloRotor + 180 * dt) % 360;

			// Modo B: Se toma una instantánea inmutable únicamente en el v-sync del monitor
			if (modoSeleccionado === 'B' && bufferCrudo.length > 0) {
				serieModoB = bufferCrudo.slice(-80);
			}

			animId = requestAnimationFrame(loopVisual);
		};

		animId = requestAnimationFrame(loopVisual);

		// Medidor de frecuencia real recibida por segundo
		const timerFrecuencia = setInterval(() => {
			muestrasRecibidasPorSeg = contadorMuestrasSegundo;
			contadorMuestrasSegundo = 0;
		}, 1000);

		return () => {
			if (worker) {
				worker.postMessage({ comando: 'DETENER' });
				worker.terminate();
				worker = null;
			}
			if (animId) cancelAnimationFrame(animId);
			clearInterval(timerFrecuencia);
		};
	});

	// Conmutador de ejecución del Worker
	function conmutarWorker() {
		if (!worker) return;
		if (workerActivo) {
			worker.postMessage({ comando: 'DETENER' });
			workerActivo = false;
		} else {
			worker.postMessage({
				comando: 'INICIAR',
				frecuenciaHz: frecuenciaSeleccionada
			});
			workerActivo = true;
		}
	}

	// Cambio dinámico de frecuencia de muestreo del sensor
	function seleccionarFrecuencia(nuevaFreq) {
		frecuenciaSeleccionada = nuevaFreq;
		if (worker && workerActivo) {
			worker.postMessage({
				comando: 'CAMBIAR_FRECUENCIA',
				frecuenciaHz: nuevaFreq
			});
		}
	}

	// Conmutación de modo arquitectural (Modo A vs Modo B)
	function seleccionarModo(nuevoModo) {
		modoSeleccionado = nuevoModo;
		// Reset de buffers para comenzar la prueba limpia
		listaModoA = [];
		bufferCrudo = [];
		serieModoB = [];
	}

	// Reinicio de contadores del ensayo
	function reiniciarEnsayo() {
		if (worker) {
			worker.postMessage({ comando: 'RESET' });
		}
		listaModoA = [];
		bufferCrudo = [];
		serieModoB = [];
		totalMuestrasAcumuladas = 0;
		muestrasRecibidasPorSeg = 0;
		contadorMuestrasSegundo = 0;
		workerActivo = false;
	}

	// Datos para LayerChart derivados según el modo activo
	const datosGrafica = $derived.by(() => {
		const datos =
			modoSeleccionado === 'A'
				? listaModoA.slice(0, 80).slice().reverse()
				: serieModoB;

		if (!datos || datos.length < 2) {
			return [
				{ id: 0, aceleracionG: 0 },
				{ id: 1, aceleracionG: 0 }
			];
		}
		return datos;
	});

	// Documentación pedagógica para el visor de código
	const archivosPedagogicos = [
		{
			nombre: 'Modo A ($state colapso)',
			descripcion:
				'FALLO DE DISEÑO: Reactividad profunda en el callback de alta frecuencia. Cada muestra física (100-1000 Hz) muta un array reactivo con unshift(), saturando el hilo de ejecución principal y provocando caídas severas de FPS (Jank).',
			codigo: `// =========================================================================
// MODO A: FALLO DE ARQUITECTURA (REACTIVIDAD PROFUNDA EN ALTA FRECUENCIA)
// =========================================================================
// El desarrollador asume erróneamente que todo evento físico debe provocar
// un ciclo inmediato de renderizado en el navegador.

let listaModoA = $state([]); // Proxy reactivo profundo en Svelte 5

// Receptor de eventos del Web Worker (100 Hz, 250 Hz, 500 Hz o 1000 Hz)
worker.onmessage = (evento) => {
  if (evento.data.tipo === 'MUESTRA') {
    const payload = evento.data.payload;

    // ERROR GRAVE: Mutación directa del array reactivo por cada muestra entrante
    // A 1000 Hz, esta línea se ejecuta 1000 veces por segundo:
    // 1. Invalida la señal reactiva listaModoA.
    // 2. Dispara la reconciliación del bloque {#each} en el DOM virtual.
    // 3. Modifica 180 nodos HTML en el layout vivo del navegador.
    // 4. Provoca "Layout Thrashing" y agotamiento de recursos.
    listaModoA.unshift({
      ...payload,
      hashCalculado: ((payload.id * 2654435761) % 4294967296).toString(16)
    });

    if (listaModoA.length > 180) {
      listaModoA.pop();
    }

    // CONSECUENCIA DIRECTA:
    // El presupuesto de frame (16.67 ms) se rompe.
    // Los FPS caen de 60 a 15-25 FPS y la interfaz tartamudea visiblemente.
  }
};`
		},
		{
			nombre: 'Modo B ($state.raw + rAF 60fps)',
			descripcion:
				'PATRÓN INDUSTRIAL: Desacoplamiento temporal entre adquisición y renderizado. Las muestras a 1000 Hz se acumulan en un array plano de JavaScript (memoria pura). Un lazo a 60 FPS coordinado con requestAnimationFrame actualiza la pantalla mediante $state.raw.',
			codigo: `// =========================================================================
// MODO B: DESACOPLAMIENTO TEMPORAL (LÍMITE FÍSICO VS. LÍMITE VISUAL)
// =========================================================================
// Patrón de arquitectura mecatrónica para SCADA, robótica y telemetría web.

// 1. Buffer plano de JavaScript: NO reactivo, memoria pura en O(1)
const bufferCrudo = [];

// 2. Estado visual inmutable Svelte 5: Solo se notifica por reemplazo de referencia
let serieModoB = $state.raw([]);

// Receptor de alta velocidad del Worker (1000 Hz)
worker.onmessage = (evento) => {
  if (evento.data.tipo === 'MUESTRA') {
    // Inserción en memoria O(1) SIN tocar el DOM ni activar señales reactivas.
    // Toma menos de 0.005 ms por muestra, dejando libre el Event Loop.
    bufferCrudo.push(evento.data.payload);
    if (bufferCrudo.length > 400) {
      bufferCrudo.splice(0, bufferCrudo.length - 400);
    }
  }
};

// 3. Lazo de renderizado desacoplado a 60 Hz (sincronizado con el monitor)
function cicloVisual() {
  if (bufferCrudo.length > 0) {
    // Se toma una instantánea inmutable de las últimas 80 muestras.
    // Al usar $state.raw, Svelte 5 solo agenda UN ÚNICO re-render por cuadro
    // de animación (máximo 60 veces por segundo, nunca 1000).
    serieModoB = bufferCrudo.slice(-80);
  }

  // Sincronización natural con el refresco de pantalla mediante V-Sync
  requestAnimationFrame(cicloVisual);
}

// Iniciar el lazo visual independiente del sensor
requestAnimationFrame(cicloVisual);`
		},
		{
			nombre: 'generador_carga.worker.js',
			descripcion:
				'Web Worker dedicado que simula el hardware embebido (IMU MPU6050 + encoder incremental de cuadratura), emitiendo ráfagas calibradas cada 10 ms para lograr con exactitud 100 Hz, 250 Hz, 500 Hz o 1000 Hz sin bloquear la interfaz.',
			codigo: `// =========================================================================
// SIMULADOR DE SENSOR MECATRÓNICO (WEB WORKER EN HILO DEDICADO)
// =========================================================================
let activo = false;
let frecuenciaHz = 100;
let contadorId = 0;
let pasosEncoder = 0;

// Temporizador calibrado a 10 ms (100 ticks por segundo)
const TICK_INTERVAL_MS = 10;

function ejecutarTick() {
  if (!activo) return;

  // Ráfagas calibradas por tick para lograr la tasa exacta de mensajes:
  // - 100 Hz  -> 1 muestra/tick  * 100 ticks/seg = 100 msgs/seg
  // - 250 Hz  -> 3 muestras/tick * 100 ticks/seg ≈ 250-300 msgs/seg
  // - 500 Hz  -> 5 muestras/tick * 100 ticks/seg = 500 msgs/seg
  // - 1000 Hz -> 10 muestras/tick * 100 ticks/seg = 1000 msgs/seg
  const muestrasPorTick = Math.max(1, Math.round(frecuenciaHz / 100));

  for (let i = 0; i < muestrasPorTick; i++) {
    contadorId++;
    const t = contadorId / frecuenciaHz;

    // Señal física: Fundamental de desbalance (28.5 Hz) + Falla rodamiento (114 Hz) + Ruido
    const aceleracionG = Math.sin(2 * Math.PI * 28.5 * t) * 1.85
                       + Math.sin(2 * Math.PI * 114.0 * t) * 0.75
                       + (Math.random() - 0.5) * 0.45;

    const velocidadRpm = 1710 + Math.sin(2 * Math.PI * 1.2 * t) * 35;
    pasosEncoder = (pasosEncoder + 16) % 65536;

    self.postMessage({
      tipo: 'MUESTRA',
      payload: {
        id: contadorId,
        timestamp: performance.now(),
        tRelativo: Number(t.toFixed(4)),
        aceleracionG: Number(aceleracionG.toFixed(3)),
        velocidadRpm: Number(velocidadRpm.toFixed(1)),
        pasosEncoder
      }
    });
  }
}

self.addEventListener('message', (e) => {
  const { comando, frecuenciaHz: freq } = e.data || {};
  if (comando === 'INICIAR') { frecuenciaHz = freq || 100; activo = true; setInterval(ejecutarTick, TICK_INTERVAL_MS); }
  if (comando === 'DETENER') { activo = false; }
  if (comando === 'CAMBIAR_FRECUENCIA') { frecuenciaHz = freq; }
});`
		}
	];
</script>

<div class="container py-5 px-3">
	<!-- Encabezado de Cátedra -->
	<nav class="breadcrumb has-succeeds-separator mb-3 is-size-7" aria-label="breadcrumbs">
		<ul>
			<li><a href="/">LPV - Clase 7</a></li>
			<li class="is-active"><a href="/proyecto-1-estres" aria-current="page">Proyecto 1: El Banco de Estrés</a></li>
		</ul>
	</nav>

	<div class="mb-5">
		<div class="is-flex is-align-items-center" style="gap: 0.75rem; flex-wrap: wrap;">
			<h1 class="title is-3 mb-0">
				<i class="fa-solid fa-gauge-high mr-2 has-text-danger"></i>
				El Banco de Estrés
			</h1>
			<span class="tag is-dark is-family-code">Límite Físico vs. Límite de Renderizado</span>
			<span class="tag is-info is-light">Svelte 5 Runes ($state.raw)</span>
		</div>
		<p class="subtitle is-6 mt-2 has-text-grey">
			Laboratorio experimental para contrastar la saturación del Event Loop en JavaScript cuando se intenta
			renderizar directamente a la frecuencia de muestreo del sensor ({frecuenciaSeleccionada} Hz) frente al desacoplamiento
			temporal a 60 FPS con <code>requestAnimationFrame</code>.
		</p>
	</div>

	<!-- Panel de Control Maestro del Banco de Pruebas -->
	<div class="card mb-5" style="border: 1px solid #cbd5e1; border-radius: 10px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);">
		<header class="card-header px-4 py-3 is-align-items-center" style="background-color: #f1f5f9; border-bottom: 1px solid #e2e8f0;">
			<div class="is-flex is-align-items-center" style="gap: 0.5rem;">
				<i class="fa-solid fa-sliders has-text-link"></i>
				<span class="has-text-weight-bold is-size-6">Consola de Control del Ensayo</span>
			</div>
			<div>
				{#if workerActivo}
					<span class="tag is-success has-text-weight-bold pulse-green">
						<i class="fa-solid fa-circle-play mr-1"></i> ADQUIRIENDO EN VIVO
					</span>
				{:else}
					<span class="tag is-dark">
						<i class="fa-solid fa-circle-stop mr-1"></i> STANDBY
					</span>
				{/if}
			</div>
		</header>

		<div class="card-content p-4">
			<div class="columns is-multiline is-vcentered">
				<!-- Botones de Inicio / Parada / Reset -->
				<div class="column is-4-desktop is-12-tablet">
					<p class="label is-size-7 mb-1 has-text-grey-dark">Control de Adquisición:</p>
					<div class="buttons has-addons mb-1">
						<button
							type="button"
							class="button is-medium {workerActivo ? 'is-danger has-text-weight-bold' : 'is-success has-text-weight-bold'}"
							onclick={conmutarWorker}
						>
							{#if workerActivo}
								<i class="fa-solid fa-stop mr-2"></i> Detener Adquisición
							{:else}
								<i class="fa-solid fa-play mr-2"></i> Iniciar Adquisición
							{/if}
						</button>
						<button
							type="button"
							class="button is-medium is-light"
							title="Reiniciar contadores y limpiar búferes"
							onclick={reiniciarEnsayo}
						>
							<i class="fa-solid fa-rotate-left mr-1"></i> Reset
						</button>
					</div>
					<div class="is-size-7 has-text-grey">
						Total Muestras: <strong>{totalMuestrasAcumuladas.toLocaleString()}</strong>
					</div>
				</div>

				<!-- Selector de Frecuencia Física -->
				<div class="column is-4-desktop is-12-tablet">
					<p class="label is-size-7 mb-1 has-text-grey-dark">Frecuencia Física del Sensor (Web Worker):</p>
					<div class="buttons has-addons mb-1">
						{#each [100, 250, 500, 1000] as f}
							<button
								type="button"
								class="button {frecuenciaSeleccionada === f ? 'is-link has-text-weight-bold' : 'is-light'}"
								onclick={() => seleccionarFrecuencia(f)}
							>
								{f} Hz
							</button>
						{/each}
					</div>
					<div class="is-size-7 has-text-grey">
						{#if frecuenciaSeleccionada === 1000}
							<span class="has-text-danger has-text-weight-bold">
								<i class="fa-solid fa-fire mr-1"></i> Máximo estrés: 1 muestra cada 1 ms
							</span>
						{:else}
							<span>Período de muestreo: {(1000 / frecuenciaSeleccionada).toFixed(1)} ms</span>
						{/if}
					</div>
				</div>

				<!-- Selector de Modo de Arquitectura (Modo A vs Modo B) -->
				<div class="column is-4-desktop is-12-tablet">
					<p class="label is-size-7 mb-1 has-text-grey-dark">Estrategia de Renderizado:</p>
					<div class="buttons has-addons mb-1">
						<button
							type="button"
							class="button {modoSeleccionado === 'A' ? 'is-danger has-text-weight-bold' : 'is-light'}"
							onclick={() => seleccionarModo('A')}
						>
							<i class="fa-solid fa-triangle-exclamation mr-1"></i> Modo A ($state)
						</button>
						<button
							type="button"
							class="button {modoSeleccionado === 'B' ? 'is-success has-text-weight-bold' : 'is-light'}"
							onclick={() => seleccionarModo('B')}
						>
							<i class="fa-solid fa-shield-halved mr-1"></i> Modo B ($state.raw)
						</button>
					</div>
					<div class="is-size-7">
						{#if modoSeleccionado === 'A'}
							<span class="has-text-danger">
								<strong>Fallo de Diseño:</strong> Mutación directa de array en cada evento
							</span>
						{:else}
							<span class="has-text-success">
								<strong>Patrón Industrial:</strong> Buffer plano + instantánea a 60 FPS
							</span>
						{/if}
					</div>
				</div>
			</div>
		</div>
	</div>

	<!-- Componente Instrumental FpsMeter: Mide FPS, Jank y Frame Budget -->
	<FpsMeter {muestrasRecibidasPorSeg} modoActual={modoSeleccionado} />

	<!-- Grilla de Instrumentación Visual: Gráfica LayerChart + Test Visual Rotor Mecatrónico -->
	<div class="columns is-multiline mb-5">
		<!-- Gráfica LayerChart en Tiempo Real -->
		<div class="column is-7-desktop is-12-tablet">
			<div class="card" style="border: 1px solid #cbd5e1; border-radius: 10px; height: 100%;">
				<header class="card-header px-4 py-3 is-align-items-center" style="background-color: #f8fafc; border-bottom: 1px solid #e2e8f0;">
					<div class="is-flex is-align-items-center is-flex-grow-1" style="gap: 0.5rem;">
						<i class="fa-solid fa-wave-square has-text-link"></i>
						<span class="has-text-weight-bold is-size-6">
							Vibración del Sensor IMU MPU-6050 (Eje Z - Aceleración)
						</span>
					</div>
					<span class="tag is-small {modoSeleccionado === 'A' ? 'is-danger' : 'is-link'} is-light">
						Escala: ±4.0 G
					</span>
				</header>

				<div class="card-content p-3">
					<!-- Contenedor estandarizado de LayerChart -->
					<div class="layerchart-box" style="height: 290px;">
						<Chart
							data={datosGrafica}
							x="id"
							xScale={scaleLinear()}
							y="aceleracionG"
							yScale={scaleLinear()}
							yDomain={[-4, 4]}
							padding={{ top: 15, right: 20, bottom: 25, left: 45 }}
						>
							<Svg>
								<Axis placement="left" grid rule format={(d) => `${d}G`} />
								<Axis placement="bottom" rule format={(d) => `#${d}`} />
								<Spline
									stroke={modoSeleccionado === 'A' ? '#dc2626' : '#2563eb'}
									stroke-width="2"
								/>
							</Svg>
						</Chart>
					</div>

					<div class="is-flex is-justify-content-between is-align-items-center mt-2 px-2 is-size-7 has-text-grey">
						<span>
							<i class="fa-solid fa-microchip mr-1"></i> MPU6050: Armónico Fundamental 28.5 Hz + Falla Rodamiento 114 Hz
						</span>
						<span>
							Muestras visibles en ventana: <strong>{datosGrafica.length}</strong>
						</span>
					</div>
				</div>
			</div>
		</div>

		<!-- Test Visual de Fluidez: Rotor Mecatrónico CSS / JS -->
		<div class="column is-5-desktop is-12-tablet">
			<div class="card" style="border: 1px solid #cbd5e1; border-radius: 10px; height: 100%;">
				<header class="card-header px-4 py-3 is-align-items-center" style="background-color: #f8fafc; border-bottom: 1px solid #e2e8f0;">
					<div class="is-flex is-align-items-center is-flex-grow-1" style="gap: 0.5rem;">
						<i class="fa-solid fa-compact-disc has-text-warning"></i>
						<span class="has-text-weight-bold is-size-6">
							Test Visual de Fluidez: Rotor Mecatrónico
						</span>
					</div>
					<span class="tag is-small {modoSeleccionado === 'A' ? 'is-danger has-text-weight-bold' : 'is-success'}">
						{modoSeleccionado === 'A' ? 'Tartamudeo (Jank)' : '60 FPS Sedoso'}
					</span>
				</header>

				<div class="card-content p-4">
					<div class="columns is-vcentered is-mobile">
						<!-- Dial Giratorio Mecánico -->
						<div class="column is-6 has-text-centered">
							<div style="display: inline-block; position: relative; width: 170px; height: 170px;">
								<svg viewBox="0 0 200 200" width="170" height="170">
									<!-- Corona exterior graduada -->
									<circle cx="100" cy="100" r="94" fill="#0f172a" stroke="#334155" stroke-width="3" />
									<circle cx="100" cy="100" r="82" fill="#1e293b" stroke="#475569" stroke-width="1.5" stroke-dasharray="3, 6" />

									<!-- Marcas radiales principales -->
									<line x1="100" y1="10" x2="100" y2="24" stroke="#e2e8f0" stroke-width="2.5" />
									<line x1="190" y1="100" x2="176" y2="100" stroke="#e2e8f0" stroke-width="2.5" />
									<line x1="100" y1="190" x2="100" y2="176" stroke="#e2e8f0" stroke-width="2.5" />
									<line x1="10" y1="100" x2="24" y2="100" stroke="#e2e8f0" stroke-width="2.5" />

									<!-- Marcas diagonales a 45° -->
									<line x1="36" y1="36" x2="46" y2="46" stroke="#94a3b8" stroke-width="1.5" />
									<line x1="164" y1="36" x2="154" y2="46" stroke="#94a3b8" stroke-width="1.5" />
									<line x1="164" y1="164" x2="154" y2="154" stroke="#94a3b8" stroke-width="1.5" />
									<line x1="36" y1="164" x2="46" y2="154" stroke="#94a3b8" stroke-width="1.5" />

									<!-- Volante de inercia acoplado al lazo rAF -->
									<g style="transform: rotate({anguloRotor}deg); transform-origin: 100px 100px;">
										<circle cx="100" cy="100" r="66" fill="#334155" opacity="0.85" />
										
										<!-- Alivios de masa en cuadrantes -->
										<circle cx="100" cy="54" r="8" fill="#1e293b" />
										<circle cx="146" cy="100" r="8" fill="#1e293b" />
										<circle cx="100" cy="146" r="8" fill="#1e293b" />
										<circle cx="54" cy="100" r="8" fill="#1e293b" />

										<!-- Aguja / Ranura indicadora de alta precisión -->
										<line
											x1="100"
											y1="100"
											x2="100"
											y2="28"
											stroke={modoSeleccionado === 'A' ? '#ef4444' : '#38bdf8'}
											stroke-width="3.5"
											stroke-linecap="round"
										/>
										<polygon
											points="100,20 94,32 106,32"
											fill={modoSeleccionado === 'A' ? '#ef4444' : '#38bdf8'}
										/>
										<!-- Contrapeso de balance -->
										<line
											x1="100"
											y1="100"
											x2="100"
											y2="124"
											stroke={modoSeleccionado === 'A' ? '#f87171' : '#7dd3fc'}
											stroke-width="2.5"
										/>
										<!-- LED estroboscópico de referencia -->
										<circle cx="100" cy="24" r="3" fill="#ffffff" />
									</g>

									<!-- Núcleo central del eje -->
									<circle cx="100" cy="100" r="14" fill="#0f172a" stroke="#94a3b8" stroke-width="2" />
									<circle cx="100" cy="100" r="5" fill="#f8fafc" />
								</svg>
							</div>
						</div>

						<!-- Telemetría instantánea de la máquina -->
						<div class="column is-6">
							<div class="mb-2">
								<div class="is-size-7 has-text-grey">Posición Angular:</div>
								<div class="is-size-5 has-text-weight-bold has-text-link is-family-monospace">
									{Math.round(anguloRotor)}°
								</div>
							</div>

							<div class="mb-2">
								<div class="is-size-7 has-text-grey">Velocidad Angular:</div>
								<div class="is-size-6 has-text-weight-bold is-family-monospace">
									{ultimaMuestra.velocidadRpm} <span class="is-size-7 has-text-grey">RPM</span>
								</div>
							</div>

							<div class="mb-2">
								<div class="is-size-7 has-text-grey">Aceleración Actual:</div>
								<div class="is-size-6 has-text-weight-bold is-family-monospace {Math.abs(ultimaMuestra.aceleracionG) > 2 ? 'has-text-danger' : 'has-text-success'}">
									{ultimaMuestra.aceleracionG > 0 ? `+${ultimaMuestra.aceleracionG}` : ultimaMuestra.aceleracionG} G
								</div>
							</div>

							<div>
								<div class="is-size-7 has-text-grey">Pulsos Encoder:</div>
								<span class="tag is-dark is-family-monospace is-small">
									#{ultimaMuestra.pasosEncoder} ticks
								</span>
							</div>
						</div>
					</div>

					<div class="notification is-light p-2 mt-2 is-size-7" style="border: 1px solid #e2e8f0; border-radius: 6px;">
						<strong>Observación Pedagógica:</strong> En Modo A a 500-1000 Hz, la saturación por micro-tareas en el hilo principal retrasa <code>requestAnimationFrame</code>. La aguja salta intervalos erráticos (<em>Jank visible</em>). En Modo B, gira a 60 FPS ininterrumpidos.
					</div>
				</div>
			</div>
		</div>
	</div>

	<!-- Tabla de Telemetría Dinámica: Bloque {#each} en Tiempo Real -->
	<div class="card mb-5" style="border: 1px solid #cbd5e1; border-radius: 10px; overflow: hidden;">
		<header class="card-header px-4 py-3 is-align-items-center" style="background-color: #f1f5f9; border-bottom: 1px solid #e2e8f0;">
			<div class="is-flex is-align-items-center is-flex-grow-1" style="gap: 0.5rem;">
				<i class="fa-solid fa-table-list has-text-link"></i>
				<span class="has-text-weight-bold is-size-6">
					Inspección de Nodos del DOM (Flujo de Muestras Entrantes)
				</span>
			</div>
			<div>
				{#if modoSeleccionado === 'A'}
					<span class="tag is-danger is-light has-text-weight-bold">
						<i class="fa-solid fa-bomb mr-1"></i> Modo A: Reconciliando {listaModoA.length} filas en cada tick
					</span>
				{:else}
					<span class="tag is-success is-light has-text-weight-bold">
						<i class="fa-solid fa-film mr-1"></i> Modo B: {serieModoB.length} filas congeladas a 60 FPS
					</span>
				{/if}
			</div>
		</header>

		<div class="card-content p-0">
			{#if modoSeleccionado === 'A'}
				<!-- Tabla Modo A: Mutación continua forzando Layout Thrashing -->
				<div class="table-container mb-0" style="max-height: 280px; overflow-y: auto;">
					<table class="table is-narrow is-fullwidth is-striped is-hoverable is-size-7 is-family-monospace mb-0">
						<thead>
							<tr style="background-color: #0f172a;">
								<th class="has-text-white"># ID</th>
								<th class="has-text-white">t Relativo</th>
								<th class="has-text-white">Aceleración (G)</th>
								<th class="has-text-white">Velocidad (RPM)</th>
								<th class="has-text-white">Encoder (Ticks)</th>
								<th class="has-text-white">Mutación Directa ($state)</th>
							</tr>
						</thead>
						<tbody>
							{#each listaModoA as item (item.id)}
								<tr>
									<td class="has-text-weight-bold">#{item.id}</td>
									<td>{item.tRelativo}s</td>
									<td>
										<span class="tag is-small {Math.abs(item.aceleracionG) > 2 ? 'is-danger' : 'is-info'} is-light">
											{item.aceleracionG > 0 ? `+${item.aceleracionG}` : item.aceleracionG} G
										</span>
									</td>
									<td>{item.velocidadRpm} RPM</td>
									<td>{item.pasosEncoder}</td>
									<td>
										<span class="tag is-small is-danger is-light">
											<i class="fa-solid fa-bolt mr-1"></i> onmessage mutó listaModoA [{item.hashCalculado}]
										</span>
									</td>
								</tr>
							{/each}
							{#if listaModoA.length === 0}
								<tr>
									<td colspan="6" class="has-text-centered has-text-grey py-5">
										<i class="fa-solid fa-circle-info mr-1"></i>
										El generador está inactivo. Presiona <strong>"Iniciar Adquisición"</strong> para comenzar a recibir muestras.
									</td>
								</tr>
							{/if}
						</tbody>
					</table>
				</div>
			{:else}
				<!-- Tabla Modo B: Instantánea desacoplada a 60 fps con $state.raw -->
				<div class="table-container mb-0" style="max-height: 280px; overflow-y: auto;">
					<table class="table is-narrow is-fullwidth is-striped is-hoverable is-size-7 is-family-monospace mb-0">
						<thead>
							<tr style="background-color: #1e3a8a;">
								<th class="has-text-white"># ID</th>
								<th class="has-text-white">t Relativo</th>
								<th class="has-text-white">Aceleración (G)</th>
								<th class="has-text-white">Velocidad (RPM)</th>
								<th class="has-text-white">Encoder (Ticks)</th>
								<th class="has-text-white">Búfer Desacoplado ($state.raw)</th>
							</tr>
						</thead>
						<tbody>
							{#each serieModoB.slice().reverse() as item (item.id)}
								<tr>
									<td class="has-text-weight-bold">#{item.id}</td>
									<td>{item.tRelativo}s</td>
									<td>
										<span class="tag is-small {Math.abs(item.aceleracionG) > 2 ? 'is-danger' : 'is-info'} is-light">
											{item.aceleracionG > 0 ? `+${item.aceleracionG}` : item.aceleracionG} G
										</span>
									</td>
									<td>{item.velocidadRpm} RPM</td>
									<td>{item.pasosEncoder}</td>
									<td>
										<span class="tag is-small is-success is-light">
											<i class="fa-solid fa-shield mr-1"></i> Instantánea V-Sync 60Hz ({serieModoB.length} muestras)
										</span>
									</td>
								</tr>
							{/each}
							{#if serieModoB.length === 0}
								<tr>
									<td colspan="6" class="has-text-centered has-text-grey py-5">
										<i class="fa-solid fa-circle-info mr-1"></i>
										El generador está inactivo. Presiona <strong>"Iniciar Adquisición"</strong> para comenzar a recibir muestras.
									</td>
								</tr>
							{/if}
						</tbody>
					</table>
				</div>
			{/if}
		</div>
	</div>

	<!-- Fundamentación Teórica de la Cátedra (FIUNA) -->
	<div class="card mb-5" style="border: 1px solid #cbd5e1; border-radius: 10px;">
		<header class="card-header px-4 py-3" style="background-color: #f8fafc; border-bottom: 1px solid #e2e8f0;">
			<span class="has-text-weight-bold is-size-6">
				<i class="fa-solid fa-graduation-cap mr-2 has-text-link"></i>
				Fundamento Teórico: Límite Físico vs. Límite de Renderizado
			</span>
		</header>
		<div class="card-content p-4">
			<div class="columns is-multiline">
				<div class="column is-6">
					<div class="notification is-light is-danger" style="height: 100%; border: 1px solid #fecaca;">
						<h5 class="title is-6 has-text-danger mb-2">
							<i class="fa-solid fa-circle-xmark mr-1"></i> Modo A: La Falsa Equivalencia
						</h5>
						<p class="is-size-7 mb-2">
							En sistemas SCADA web o dashboards de telemetría, los desarrolladores novatos tienden a creer que "reactividad" significa hacer que cada evento del sensor modifique una variable reactiva en la vista.
						</p>
						<p class="is-size-7 mb-2">
							A <strong>1000 Hz</strong>, el sensor genera una muestra cada <strong>1 ms</strong>. El monitor humano a 60 Hz solo se refresca cada <strong>16.67 ms</strong>. Intentar renderizar 1000 veces por segundo obliga al motor de JavaScript a recalcular estilos y geometrías 940 veces en vano, colapsando el hilo único del navegador.
						</p>
						<div class="tags has-addons mb-0">
							<span class="tag is-danger">Resultado:</span>
							<span class="tag is-white">Jank, Stuttering, Event Loop Bloqueado</span>
						</div>
					</div>
				</div>

				<div class="column is-6">
					<div class="notification is-light is-success" style="height: 100%; border: 1px solid #bbf7d0;">
						<h5 class="title is-6 has-text-success mb-2">
							<i class="fa-solid fa-circle-check mr-1"></i> Modo B: El Patrón de Desacoplamiento
						</h5>
						<p class="is-size-7 mb-2">
							La regla de oro del diseño mecatrónico visual es: <em>"Nunca permitas que la frecuencia de muestreo del hardware gobierne la tasa de renderizado de la interfaz de usuario"</em>.
						</p>
						<p class="is-size-7 mb-2">
							Se utiliza un <strong>buffer plano no reactivo</strong> en memoria RAM donde el Worker deposita las muestras en tiempo O(1). Un lazo regulado por <code>requestAnimationFrame</code> toma instantáneas inmutables a 60 FPS usando <code>$state.raw</code>, manteniendo el presupuesto de frame en &lt; 16.67 ms sin importar si el sensor corre a 100 Hz o a 10.000 Hz.
						</p>
						<div class="tags has-addons mb-0">
							<span class="tag is-success">Resultado:</span>
							<span class="tag is-white">60 FPS Sedosos, Hilo Libre, Consolidación Precisa</span>
						</div>
					</div>
				</div>
			</div>
		</div>
	</div>

	<!-- Visor Pedagógico de Código Fuente -->
	<CodeViewer
		titulo="Código Fuente del Laboratorio (Modo A vs. Modo B)"
		archivos={archivosPedagogicos}
	/>
</div>
