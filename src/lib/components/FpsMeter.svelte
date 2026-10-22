<script>
	/**
	 * Componente FpsMeter: Medidor instrumental de FPS, Jank y Frame Budget.
	 * Evalúa el impacto de la carga de eventos en el Event Loop de JavaScript.
	 *
	 * Cátedra: Lenguajes de Programación Visual (LPV) - FIUNA
	 * Proyecto 1: "El Banco de Estrés"
	 */

	let { muestrasRecibidasPorSeg = 0, modoActual = 'B' } = $props();

	let fps = $state(60);
	let maxFrameMs = $state(16.7);
	let jankFrames = $state(0);
	let deltaInstantaneoMs = $state(16.6);

	// Lazo rAF para medición precisa de frames del hilo principal
	$effect(() => {
		let framesContados = 0;
		let jankAcumulado = 0;
		let peorDelta = 0;
		let ultimoSegundo = performance.now();
		let ultimoFrame = performance.now();
		let animId;

		const medir = (ahora) => {
			const delta = ahora - ultimoFrame;
			ultimoFrame = ahora;
			deltaInstantaneoMs = Math.round(delta * 10) / 10;

			framesContados++;
			if (delta > peorDelta) {
				peorDelta = delta;
			}

			// Jank: Si el frame demora más de 28 ms (~2 períodos de 60 Hz), se considera frame perdido
			if (delta > 28) {
				jankAcumulado++;
			}

			// Consolidación de métricas al cumplirse 1000 ms
			if (ahora - ultimoSegundo >= 1000) {
				const lapsoReal = (ahora - ultimoSegundo) / 1000;
				fps = Math.round(framesContados / lapsoReal);
				maxFrameMs = Math.min(999, Math.round(peorDelta * 10) / 10);
				jankFrames = jankAcumulado;

				framesContados = 0;
				jankAcumulado = 0;
				peorDelta = 0;
				ultimoSegundo = ahora;
			}

			animId = requestAnimationFrame(medir);
		};

		animId = requestAnimationFrame(medir);

		return () => {
			if (animId) cancelAnimationFrame(animId);
		};
	});

	// Ratio de desacoplamiento físico vs visual
	const ratioDesacoplamiento = $derived(
		(muestrasRecibidasPorSeg / Math.max(1, fps)).toFixed(1)
	);

	// Diagnóstico de salud de refresco visual
	const saludFps = $derived.by(() => {
		if (fps >= 55) {
			return { color: 'is-success', texto: '60 FPS Óptimo', badge: 'is-success' };
		}
		if (fps >= 35) {
			return { color: 'is-warning', texto: 'Jank / Degradación', badge: 'is-warning' };
		}
		return { color: 'is-danger', texto: 'Colapso de Hilo', badge: 'is-danger' };
	});

	// Diagnóstico del presupuesto de frame (16.67 ms para 60 FPS)
	const saludPresupuesto = $derived.by(() => {
		if (maxFrameMs <= 18) {
			return { color: 'is-success', texto: 'Dentro de margen (<16.7 ms)' };
		}
		if (maxFrameMs <= 33) {
			return { color: 'is-warning', texto: 'Sobrepaso (16.7 - 33 ms)' };
		}
		return { color: 'is-danger', texto: 'Bloqueo Crítico (>33 ms)' };
	});
</script>

<div class="card mb-5" style="border: 1px solid #cbd5e1; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);">
	<header class="card-header px-4 py-3 is-align-items-center" style="background-color: #0f172a;">
		<div class="is-flex is-align-items-center is-flex-grow-1" style="gap: 0.6rem;">
			<span class="icon has-text-warning">
				<i class="fa-solid fa-gauge-high"></i>
			</span>
			<span class="has-text-weight-bold has-text-white is-size-6">
				Telemetría de Rendimiento del Navegador (Event Loop & Frame Budget)
			</span>
		</div>
		<div>
			{#if modoActual === 'A'}
				<span class="tag is-danger is-light has-text-weight-bold">
					<i class="fa-solid fa-triangle-exclamation mr-1"></i> Modo A: Fallo de Diseño
				</span>
			{:else}
				<span class="tag is-success is-light has-text-weight-bold">
					<i class="fa-solid fa-circle-check mr-1"></i> Modo B: Desacoplado 60 FPS
				</span>
			{/if}
		</div>
	</header>

	<div class="card-content p-4" style="background-color: #f8fafc;">
		<div class="columns is-multiline is-variable is-3">
			<!-- 1. Frecuencia Física -->
			<div class="column is-3-desktop is-6-tablet">
				<div class="box p-3 has-background-white" style="border: 1px solid #e2e8f0; height: 100%;">
					<div class="is-flex is-justify-content-between is-align-items-center mb-1">
						<span class="is-size-7 has-text-grey-dark has-text-weight-semibold">Frecuencia Física Entrada</span>
						<span class="tag is-small is-info is-light">Sensor Físico</span>
					</div>
					<div class="is-size-3 has-text-weight-bold has-text-info my-1">
						{muestrasRecibidasPorSeg} <span class="is-size-6 has-text-grey">Hz</span>
					</div>
					<progress
						class="progress is-info is-small mb-2"
						value={muestrasRecibidasPorSeg}
						max="1000"
					></progress>
					<div class="is-size-7 has-text-grey">
						Ráfagas del Web Worker (0 - 1000 Hz)
					</div>
				</div>
			</div>

			<!-- 2. Refresco Visual (FPS) -->
			<div class="column is-3-desktop is-6-tablet">
				<div class="box p-3 has-background-white" style="border: 1px solid #e2e8f0; height: 100%;">
					<div class="is-flex is-justify-content-between is-align-items-center mb-1">
						<span class="is-size-7 has-text-grey-dark has-text-weight-semibold">Tasa Refresco Visual</span>
						<span class="tag is-small {saludFps.badge}">{saludFps.texto}</span>
					</div>
					<div class="is-size-3 has-text-weight-bold my-1 {fps >= 50 ? 'has-text-success' : fps >= 30 ? 'has-text-warning' : 'has-text-danger'}">
						{fps} <span class="is-size-6 has-text-grey">/ 60 FPS</span>
					</div>
					<progress
						class="progress {saludFps.color} is-small mb-2"
						value={Math.min(60, fps)}
						max="60"
					></progress>
					<div class="is-size-7 has-text-grey">
						Límite visual del monitor (V-Sync)
					</div>
				</div>
			</div>

			<!-- 3. Presupuesto de Frame -->
			<div class="column is-3-desktop is-6-tablet">
				<div class="box p-3 has-background-white" style="border: 1px solid #e2e8f0; height: 100%;">
					<div class="is-flex is-justify-content-between is-align-items-center mb-1">
						<span class="is-size-7 has-text-grey-dark has-text-weight-semibold">Presupuesto de Frame</span>
						<span class="tag is-small {saludPresupuesto.color} is-light">Límite 16.67 ms</span>
					</div>
					<div class="is-size-3 has-text-weight-bold my-1 {maxFrameMs <= 18 ? 'has-text-success' : maxFrameMs <= 35 ? 'has-text-warning' : 'has-text-danger'}">
						{maxFrameMs} <span class="is-size-6 has-text-grey">ms</span>
					</div>
					<progress
						class="progress {saludPresupuesto.color} is-small mb-2"
						value={Math.min(50, maxFrameMs)}
						max="50"
					></progress>
					<div class="is-size-7 has-text-grey">
						Peor latencia en el último segundo
					</div>
				</div>
			</div>

			<!-- 4. Ratio de Desacoplamiento -->
			<div class="column is-3-desktop is-6-tablet">
				<div class="box p-3 has-background-white" style="border: 1px solid #e2e8f0; height: 100%;">
					<div class="is-flex is-justify-content-between is-align-items-center mb-1">
						<span class="is-size-7 has-text-grey-dark has-text-weight-semibold">Ratio Desacoplamiento</span>
						<span class="tag is-small is-primary is-light">Físico / Visual</span>
					</div>
					<div class="is-size-3 has-text-weight-bold has-text-primary my-1">
						{ratioDesacoplamiento} <span class="is-size-6 has-text-grey">: 1</span>
					</div>
					<progress
						class="progress is-primary is-small mb-2"
						value={Math.min(20, Number(ratioDesacoplamiento))}
						max="20"
					></progress>
					<div class="is-size-7 has-text-grey">
						Muestras consolidadas por frame
					</div>
				</div>
			</div>
		</div>

		<!-- Barra de diagnóstico en vivo y conteo de Jank -->
		<div class="notification is-light p-3 mt-2 {modoActual === 'A' && fps < 45 ? 'is-danger' : 'is-info'}" style="border: 1px solid rgba(0,0,0,0.08); border-radius: 6px;">
			<div class="is-flex is-justify-content-between is-align-items-center is-flex-wrap-wrap" style="gap: 0.5rem;">
				<div class="is-size-7">
					{#if modoActual === 'A'}
						<i class="fa-solid fa-triangle-exclamation mr-1 has-text-danger"></i>
						<strong>Alerta Modo A:</strong> Mutar <code>$state</code> directamente por cada muestra a {muestrasRecibidasPorSeg} Hz obliga al motor a reconciliar el DOM continuamente.
					{:else}
						<i class="fa-solid fa-shield-halved mr-1 has-text-success"></i>
						<strong>Aislamiento Modo B:</strong> Las {muestrasRecibidasPorSeg} muestras/segundo entran en memoria plana (<code>bufferCrudo</code>) sin tocar el DOM. La interfaz corre a 60 FPS estables.
					{/if}
				</div>

				<div class="tags has-addons mb-0">
					<span class="tag is-dark is-size-7">Frames con Jank (&gt;28ms)</span>
					<span class="tag is-size-7 {jankFrames > 0 ? 'is-danger has-text-weight-bold blink-red-critical' : 'is-success'}">
						{jankFrames} / seg
					</span>
					<span class="tag is-light is-size-7">Delta: {deltaInstantaneoMs} ms</span>
				</div>
			</div>
		</div>
	</div>
</div>
