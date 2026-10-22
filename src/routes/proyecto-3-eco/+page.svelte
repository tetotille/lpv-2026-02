<script>
	/**
	 * Proyecto 3: "El Eco Visual" (Consigna Administrativa vs. Realimentación Física)
	 * Cátedra: Lenguajes de Programación Visual — Facultad de Ingeniería (UNA)
	 *
	 * Demuestra la discrepancia temporal intrínseca entre:
	 * - Tiempo Real Administrativo (Soft): El DOM actualiza el Setpoint r(t) en < 1 ms mediante bind:value.
	 * - Tiempo Real Físico (Hard/Mecatrónico): El rotor posee masa inercial J, fricción viscosa B
	 *   y sufre retardo de red T_d, respondiendo a una ecuación diferencial de segundo orden.
	 */

	import { Chart, Svg, Spline, Axis } from 'layerchart';
	import { scaleLinear } from 'd3-scale';
	import CodeViewer from '$lib/components/CodeViewer.svelte';
	import TachometerSvg from '$lib/components/TachometerSvg.svelte';

	// 1. Estados de Consigna Administrativa y Simulación (Svelte 5 Runes)
	let consigna = $state(1500);
	let rpmReal = $state(0);
	let velocidadCambio = $state(0); // d(rpm)/dt
	let aceleracionAngular = $state(0); // rad/s^2
	let parElectromagnetico = $state(0); // N·m
	let tiempoSimulado = $state(0);
	let perfilSeleccionado = $state('servomotor');
	let retardoTdMs = $state(0);
	let enPausa = $state(false);

	// Catálogo pedagógico de Perfiles Mecánicos de la Planta (Inercia J y Amortiguamiento zeta)
	const perfiles = [
		{
			id: 'servomotor',
			nombre: 'Servomotor Ligero',
			tau: 0.35,
			zeta: 0.9,
			wn: 4.5,
			inerciaJ: 0.015,
			amortiguamientoB: 0.002,
			etiqueta: 'tau = 0.35 s, zeta = 0.90',
			descripcion: 'Respuesta rápida y crítica sin sobreimpulso. Actuador mecatrónico de baja inercia.',
			icono: 'fa-bolt',
			tagColor: 'is-info'
		},
		{
			id: 'turbina',
			nombre: 'Turbina / Volante Pesado',
			tau: 1.6,
			zeta: 1.15,
			wn: 1.0,
			inerciaJ: 0.45,
			amortiguamientoB: 0.005,
			etiqueta: 'tau = 1.60 s, zeta = 1.15',
			descripcion: 'Respuesta lenta y sobreamortiguada. Elevada masa rotante que acumula energía cinética.',
			icono: 'fa-dharmachakra',
			tagColor: 'is-dark'
		},
		{
			id: 'flexible',
			nombre: 'Eje Flexible Subamortiguado',
			tau: 0.65,
			zeta: 0.35,
			wn: 4.0,
			inerciaJ: 0.05,
			amortiguamientoB: 0.001,
			etiqueta: 'tau = 0.65 s, zeta = 0.35',
			descripcion: 'Presenta sobreimpulso (overshoot ~31%) y oscilaciones antes de estabilizarse en la consigna.',
			icono: 'fa-wave-square',
			tagColor: 'is-warning'
		}
	];

	// Perfil mecánico activo derivado
	const perfilActual = $derived(
		perfiles.find((p) => p.id === perfilSeleccionado) || perfiles[0]
	);

	// Estado de Convergencia de Interfaz (Atenuación de Interfaz)
	// Cuando el actuador aún está acelerando/frenando, la UI debe advertir "En Tránsito"
	const enTransito = $derived(
		Math.abs(consigna - rpmReal) > 15 || Math.abs(velocidadCambio) > 20
	);

	// Error instantáneo de lazo de control
	const errorLazo = $derived(Math.round(consigna - rpmReal));

	// 2. Búfer superficial reactivo para LayerChart ($state.raw para evitar mutación profunda)
	let historial = $state.raw([
		{ t: 0, consigna: 1500, rpmReal: 0 },
		{ t: 0.05, consigna: 1500, rpmReal: 0 }
	]);

	// Estadísticas del escalón dinámico
	let consignaPrevia = 1500;
	let tiempoInicioEscalon = 0;
	let picoMaximoRpm = 0;
	let sobreimpulsoPct = $state(0);
	let tiempoSubidaS = $state(0);

	// 3. Simulación Física de 2do Orden a 40 Hz (25 ms) en $effect
	$effect(() => {
		const dt = 0.025; // Paso de integración numérica Euler (25 ms)
		let colaRetardo = [];
		let tLocal = 0;
		let contadorMuestreo = 0;

		const intervalId = setInterval(() => {
			if (enPausa) return;

			tLocal += dt;
			tiempoSimulado = Number(tLocal.toFixed(2));

			// Almacenar en la cola FIFO de retardo de transporte
			colaRetardo.push({ t: tLocal, val: consigna });
			if (colaRetardo.length > 250) {
				colaRetardo.shift();
			}

			// Detección de nuevo escalón para métricas transitorias
			if (consigna !== consignaPrevia) {
				consignaPrevia = consigna;
				tiempoInicioEscalon = tLocal;
				picoMaximoRpm = rpmReal;
				sobreimpulsoPct = 0;
				tiempoSubidaS = 0;
			}

			// Obtener entrada u(t - Td) según retardo de red inyectado
			let u = consigna;
			if (retardoTdMs > 0) {
				const tObjetivo = tLocal - retardoTdMs / 1000;
				for (let i = colaRetardo.length - 1; i >= 0; i--) {
					if (colaRetardo[i].t <= tObjetivo) {
						u = colaRetardo[i].val;
						break;
					}
				}
			}

			// Parámetros de la EDO de 2do orden del perfil actual
			const wn = perfilActual.wn;
			const zeta = perfilActual.zeta;
			const J = perfilActual.inerciaJ;
			const B = perfilActual.amortiguamientoB;

			// Ecuación diferencial: d2y/dt2 + 2*zeta*wn*dy/dt + wn^2*y = wn^2 * u
			// d2y/dt2 = wn^2 * (u - y) - 2*zeta*wn * (dy/dt)
			const aceleracionRpm = wn * wn * (u - rpmReal) - 2 * zeta * wn * velocidadCambio;
			velocidadCambio += aceleracionRpm * dt;
			rpmReal += velocidadCambio * dt;

			// Protección de no negatividad para actuador unidireccional
			if (rpmReal < 0) {
				rpmReal = 0;
				if (velocidadCambio < 0) velocidadCambio = 0;
			}

			// Conversión de unidades mecatrónicas
			// Aceleración angular alpha en rad/s^2 = (d(rpm)/dt) * (2*pi / 60)
			const alpha = velocidadCambio * (Math.PI / 30);
			aceleracionAngular = alpha;

			// Velocidad angular omega en rad/s = rpm * (2*pi / 60)
			const omega = rpmReal * (Math.PI / 30);

			// Par electromagnético estimado: tau_em = J * alpha + B * omega
			parElectromagnetico = J * alpha + B * omega;

			// Monitoreo de sobreimpulso y tiempo de subida
			if (rpmReal > picoMaximoRpm) {
				picoMaximoRpm = rpmReal;
			}
			if (consigna > 0 && picoMaximoRpm > consigna) {
				sobreimpulsoPct = Number((((picoMaximoRpm - consigna) / consigna) * 100).toFixed(1));
			}
			if (tiempoSubidaS === 0 && consigna > 0 && rpmReal >= 0.9 * consigna) {
				tiempoSubidaS = Number((tLocal - tiempoInicioEscalon).toFixed(2));
			}

			// Muestreo para LayerChart (cada 50 ms = 20 Hz, búfer inmutable $state.raw)
			contadorMuestreo++;
			if (contadorMuestreo % 2 === 0) {
				const nuevoPunto = {
					t: Number(tLocal.toFixed(2)),
					consigna,
					rpmReal: Number(rpmReal.toFixed(1))
				};
				// Mantiene ventana deslizante de 140 muestras (7.0 segundos de historial visible)
				const recorte =
					historial.length >= 140
						? historial.slice(historial.length - 139)
						: historial;
				historial = [...recorte, nuevoPunto];
			}
		}, 25);

		return () => {
			clearInterval(intervalId);
		};
	});

	// Métodos de control del laboratorio
	function aplicarEscalon(valor) {
		consigna = valor;
	}

	function reiniciarLaboratorio() {
		consigna = 0;
		rpmReal = 0;
		velocidadCambio = 0;
		aceleracionAngular = 0;
		parElectromagnetico = 0;
		picoMaximoRpm = 0;
		sobreimpulsoPct = 0;
		tiempoSubidaS = 0;
		historial = [
			{ t: 0, consigna: 0, rpmReal: 0 },
			{ t: 0.05, consigna: 0, rpmReal: 0 }
		];
	}

	// Fragmentos pedagógicos de código fuente para el visor didáctico CodeViewer
	const codigoTachometer = `<script>
  let {
    consigna = 0,
    valorReal = 0,
    maxRpm = 3000,
    unidad = 'RPM',
    amortiguacionCssMs = 60
  } = $props();

  const cx = 170;
  const cy = 165;

  // Mapeo angular: 0..3000 RPM -> -135° a +135° (270° de barrido)
  function rpmAAngulo(rpm) {
    const clamped = Math.min(Math.max(rpm, -150), maxRpm * 1.15);
    return -135 + (clamped / maxRpm) * 270;
  }

  const anguloConsigna = $derived(rpmAAngulo(consigna));
  const anguloReal = $derived(rpmAAngulo(valorReal));
<\/script>

<svg viewBox="0 0 340 300">
  <!-- Sector de discrepancia angular e(t) = r(t) - y(t) -->
  {#if Math.abs(anguloConsigna - anguloReal) > 0.4}
    <path d={pathDiscrepancia} fill="rgba(245, 158, 11, 0.35)" stroke="#f59e0b" stroke-dasharray="4 2" />
  {/if}

  <!-- Aguja 1: Consigna Administrativa (Azul - Instantánea en el DOM) -->
  <g style="transform: rotate({anguloConsigna}deg); transform-origin: 170px 165px; transition: none;">
    <line x1="170" y1="165" x2="170" y2="38" stroke="#2563eb" stroke-width="2.6" />
    <polygon points="165.5,48 174.5,48 170,33" fill="#2563eb" />
  </g>

  <!-- Aguja 2: Realimentación Física (Roja - Amortiguación Mecánica CSS) -->
  <g style="transform: rotate({anguloReal}deg); transform-origin: 170px 165px; transition: transform {amortiguacionCssMs}ms linear;">
    <polygon points="166,165 168.6,52 170,42 171.4,52 174,165 172.5,188 167.5,188" fill="#dc2626" />
  </g>
</svg>`;

	const codigoPagina = `<script>
  import { Chart, Svg, Spline, Axis } from 'layerchart';
  import { scaleLinear } from 'd3-scale';

  let consigna = $state(1500);
  let rpmReal = $state(0);
  let velocidadCambio = $state(0);
  let historial = $state.raw([]);

  // Indicador de Atenuación de Interfaz para prevenir el síndrome de doble clic
  const enTransito = $derived(
    Math.abs(consigna - rpmReal) > 15 || Math.abs(velocidadCambio) > 20
  );

  // Lazo Físico a 40 Hz (25 ms) con resolución de la EDO de 2do orden
  $effect(() => {
    const dt = 0.025;
    const interval = setInterval(() => {
      // Retardo de red T_d y parámetros mecánicos J, wn, zeta
      const u = obtenerEntradaConRetardo(consigna, retardoTdMs);
      const d2y = wn * wn * (u - rpmReal) - 2 * zeta * wn * velocidadCambio;
      velocidadCambio += d2y * dt;
      rpmReal += velocidadCambio * dt;

      // Actualizar buffer inmutable para LayerChart
      historial = [...historial.slice(-140), { t: tiempo, consigna, rpmReal }];
    }, 25);
    return () => clearInterval(interval);
  });
<\/script>

<!-- LayerChart superpone ambas realidades temporales -->
<div class="layerchart-box">
  <Chart data={historial} x="t" xScale={scaleLinear()} yScale={scaleLinear()} yDomain={[0, 3500]}>
    <Svg>
      <Axis placement="left" label="RPM" />
      <Axis placement="bottom" label="Tiempo (s)" />
      <Spline y="consigna" stroke="#2563eb" strokeWidth={2} strokeDasharray="5 3" />
      <Spline y="rpmReal" stroke="#dc2626" strokeWidth={2.5} />
    </Svg>
  </Chart>
</div>`;
</script>

<svelte:head>
	<title>Proyecto 3: El Eco Visual — Consigna vs. Realimentación Física</title>
</svelte:head>

<!-- Migas de Pan / Breadcrumbs -->
<nav class="breadcrumb has-arrow-separator mb-4" aria-label="breadcrumbs">
	<ul>
		<li><a href="/" class="has-text-grey"><i class="fa-solid fa-house mr-1"></i> Portal</a></li>
		<li><a href="/" class="has-text-grey">Laboratorios</a></li>
		<li class="is-active">
			<a href="/proyecto-3-eco" aria-current="page" class="has-text-link has-text-weight-bold">
				<i class="fa-solid fa-compass-drafting mr-1"></i> Proyecto 3: El Eco Visual
			</a>
		</li>
	</ul>
</nav>

<!-- Encabezado / Hero del Proyecto -->
<div class="box p-5 mb-5" style="border-left: 5px solid #2563eb; border-radius: 10px;">
	<div class="is-flex is-justify-content-space-between is-align-items-center" style="flex-wrap: wrap; gap: 0.5rem;">
		<div>
			<div class="tags has-addons mb-2">
				<span class="tag is-dark is-family-code">PROYECTO 03</span>
				<span class="tag is-info has-text-weight-bold">DINÁMICA DE LAZO CERRADO</span>
				<span class="tag is-light is-family-code">Svelte 5 Runes + LayerChart</span>
			</div>
			<h1 class="title is-3 mb-2">
				El Eco Visual: Consigna Administrativa vs. Realimentación Física
			</h1>
			<p class="subtitle is-6 has-text-grey mb-0">
				Supervisión gráfica de actuadores rotativos con <strong>inercia mecánica ($J$)</strong>, <strong>amortiguamiento ($\zeta$)</strong> y <strong>retardo de transporte de red ($T_d$)</strong>.
			</p>
		</div>

		<div class="buttons">
			<button
				type="button"
				class="button is-small {enPausa ? 'is-warning' : 'is-light'}"
				onclick={() => (enPausa = !enPausa)}
			>
				<i class="fa-solid {enPausa ? 'fa-play' : 'fa-pause'} mr-1"></i>
				{enPausa ? 'Reanudar Simulación' : 'Pausar Simulación'}
			</button>
			<button
				type="button"
				class="button is-small is-light"
				onclick={reiniciarLaboratorio}
			>
				<i class="fa-solid fa-rotate-left mr-1"></i> Reiniciar
			</button>
		</div>
	</div>
</div>

<!-- Layout Principal de Laboratorio (2 Columnas) -->
<div class="columns is-multiline">
	<!-- Columna Izquierda: Tacómetro SVG de Doble Aguja y Estado del Actuador -->
	<div class="column is-12-tablet is-5-desktop">
		<div class="card concept-card" style="box-shadow: 0 4px 12px rgba(15, 23, 42, 0.06);">
			<header class="card-header px-4 py-3" style="background: #f8fafc; border-bottom: 1px solid #e2e8f0;">
				<div class="is-flex is-align-items-center is-justify-content-space-between is-flex-grow-1">
					<span class="has-text-weight-bold is-size-6">
						<i class="fa-solid fa-gauge-high mr-2 has-text-info"></i>
						Tacómetro Vectorial Doble Aguja
					</span>
					<span class="tag is-info is-light is-family-code is-size-7">
						Lazo 40 Hz (25 ms)
					</span>
				</div>
			</header>

			<div class="card-content p-4">
				<!-- Tacómetro Circular SVG de Alta Precisión -->
				<TachometerSvg
					consigna={consigna}
					valorReal={rpmReal}
					maxRpm={3000}
					unidad="RPM"
					amortiguacionCssMs={50}
				/>

				<!-- Indicador de Atenuación de Interfaz (Estado En Tránsito) -->
				{#if enTransito}
					<div
						class="notification is-warning is-light p-3 mt-3 pulse-amber"
						style="border-left: 4px solid #d97706; border-radius: 8px;"
					>
						<div class="is-flex is-align-items-center mb-1">
							<i class="fa-solid fa-hourglass-half mr-2 has-text-warning-dark fa-spin"></i>
							<strong class="is-size-7 has-text-warning-dark">
								⏳ ACTUADOR EN TRÁNSITO — CONVERGIENDO INERCIA MECÁNICA
							</strong>
						</div>
						<p class="is-size-7 has-text-grey-dark mb-0">
							<strong>¿Por qué informar al operador?</strong> En la supervisión industrial, la interfaz debe acusar recibo inmediato de que la consigna fue despachada. De lo contrario, la falta de respuesta visual instantánea incita al operador a <em>aporrear el mando</em> ("síndrome del doble clic"), provocando sobrecorrientes en el variador y sobreimpulso innecesario.
						</p>
					</div>
				{:else}
					<div
						class="notification is-success is-light p-3 mt-3"
						style="border-left: 4px solid #16a34a; border-radius: 8px;"
					>
						<div class="is-flex is-align-items-center mb-1">
							<i class="fa-solid fa-circle-check mr-2 has-text-success"></i>
							<strong class="is-size-7 has-text-success-dark">
								✅ RÉGIMEN PERMANENTE — CONSIGNAS ALINEADAS
							</strong>
						</div>
						<p class="is-size-7 has-text-grey-dark mb-0">
							El rotor alcanzó la consigna de <strong>{consigna} RPM</strong> dentro de la banda de tolerancia (|e(t)| &le; 15 RPM). El par motor electromagnético se estabilizó contra la carga viscosa.
						</p>
					</div>
				{/if}

				<!-- Telemetría Dinámica de Planta (4 Métricas Clave) -->
				<div class="columns is-mobile is-multiline mt-2 mb-0">
					<div class="column is-6 py-2">
						<div class="p-2 has-background-white-bis" style="border-radius: 6px; border: 1px solid #e2e8f0;">
							<span class="is-size-7 has-text-grey is-block">Velocidad Angular $\omega$</span>
							<strong class="is-size-6 has-text-danger is-family-code">
								{(rpmReal * 0.10472).toFixed(1)} <span class="is-size-7">rad/s</span>
							</strong>
						</div>
					</div>
					<div class="column is-6 py-2">
						<div class="p-2 has-background-white-bis" style="border-radius: 6px; border: 1px solid #e2e8f0;">
							<span class="is-size-7 has-text-grey is-block">Aceleración Angular $\alpha$</span>
							<strong class="is-size-6 has-text-dark is-family-code">
								{aceleracionAngular.toFixed(1)} <span class="is-size-7">rad/s²</span>
							</strong>
						</div>
					</div>
					<div class="column is-6 py-2">
						<div class="p-2 has-background-white-bis" style="border-radius: 6px; border: 1px solid #e2e8f0;">
							<span class="is-size-7 has-text-grey is-block">Par Electromagnético $\tau$</span>
							<strong class="is-size-6 has-text-link is-family-code">
								{parElectromagnetico.toFixed(2)} <span class="is-size-7">N·m</span>
							</strong>
						</div>
					</div>
					<div class="column is-6 py-2">
						<div class="p-2 has-background-white-bis" style="border-radius: 6px; border: 1px solid #e2e8f0;">
							<span class="is-size-7 has-text-grey is-block">Retardo de Red $T_d$</span>
							<strong class="is-size-6 has-text-warning-dark is-family-code">
								{retardoTdMs} <span class="is-size-7">ms</span>
							</strong>
						</div>
					</div>
				</div>
			</div>
		</div>
	</div>

	<!-- Columna Derecha: Panel de Mando Administrativo y Curvas LayerChart -->
	<div class="column is-12-tablet is-7-desktop">
		<!-- Tarjeta 1: Panel de Mando Administrativo (bind:value y Escalones) -->
		<div class="card concept-card mb-4" style="box-shadow: 0 4px 12px rgba(15, 23, 42, 0.06);">
			<header class="card-header px-4 py-3" style="background: #f8fafc; border-bottom: 1px solid #e2e8f0;">
				<div class="is-flex is-align-items-center is-justify-content-space-between is-flex-grow-1">
					<span class="has-text-weight-bold is-size-6">
						<i class="fa-solid fa-sliders mr-2 has-text-link"></i>
						Panel de Mando Administrativo (DOM Inmediato)
					</span>
					<span class="tag is-link is-light is-family-code is-size-7">
						bind:value en microsegundos
					</span>
				</div>
			</header>

			<div class="card-content p-4">
				<!-- Control Deslizante (Slider Continuo) -->
				<div class="field mb-3">
					<div class="is-flex is-justify-content-space-between is-align-items-center mb-1">
						<label class="label mb-0 is-size-6" for="sliderConsigna">
							<i class="fa-solid fa-crosshairs mr-1 has-text-link"></i>
							Consigna Administrativa de Operador $r(t)$:
						</label>
						<span class="tag is-link is-medium has-text-weight-bold is-family-code">
							{consigna} RPM
						</span>
					</div>
					<input
						id="sliderConsigna"
						class="slider is-fullwidth is-link mb-1"
						type="range"
						min="0"
						max="3000"
						step="10"
						bind:value={consigna}
					/>
					<div class="is-flex is-justify-content-space-between is-size-7 has-text-grey px-1">
						<span>0 RPM (0%)</span>
						<span>750 (25%)</span>
						<span>1500 (50%)</span>
						<span>2250 (75%)</span>
						<span>3000 RPM (100%)</span>
					</div>
				</div>

				<!-- Botones de Escalón Brusco (Step Input) -->
				<div class="mb-4">
					<span class="is-size-7 has-text-weight-bold has-text-grey-dark is-block mb-2">
						Inyección de Escalones Bruscos (Step Inputs de Control Clásico):
					</span>
					<div class="buttons are-small mb-0">
						<button
							type="button"
							class="button {consigna === 0 ? 'is-danger is-focused has-text-weight-bold' : 'is-white'}"
							onclick={() => aplicarEscalon(0)}
						>
							<i class="fa-solid fa-stop mr-1"></i> 0 RPM (Parada)
						</button>
						<button
							type="button"
							class="button {consigna === 750 ? 'is-link is-focused has-text-weight-bold' : 'is-light'}"
							onclick={() => aplicarEscalon(750)}
						>
							750 RPM (25%)
						</button>
						<button
							type="button"
							class="button {consigna === 1500 ? 'is-link is-focused has-text-weight-bold' : 'is-light'}"
							onclick={() => aplicarEscalon(1500)}
						>
							1500 RPM (50%)
						</button>
						<button
							type="button"
							class="button {consigna === 2400 ? 'is-link is-focused has-text-weight-bold' : 'is-light'}"
							onclick={() => aplicarEscalon(2400)}
						>
							2400 RPM (80%)
						</button>
						<button
							type="button"
							class="button {consigna === 3000 ? 'is-danger is-focused has-text-weight-bold' : 'is-light'}"
							onclick={() => aplicarEscalon(3000)}
						>
							<i class="fa-solid fa-forward-fast mr-1"></i> 3000 RPM (Plena Carga)
						</button>
					</div>
				</div>

				<!-- Selector de Perfil Mecánico de la Planta -->
				<div class="mb-4">
					<span class="is-size-7 has-text-weight-bold has-text-grey-dark is-block mb-2">
						Perfil Mecánico de la Planta (Inercia $J$ y Factor de Amortiguamiento $\zeta$):
					</span>
					<div class="columns is-multiline is-variable is-2">
						{#each perfiles as perfil (perfil.id)}
							<div class="column is-4">
								<button
									type="button"
									class="box p-3 has-text-left is-clickable is-fullwidth"
									style="border: 2px solid {perfilSeleccionado === perfil.id
										? '#2563eb'
										: '#e2e8f0'}; background: {perfilSeleccionado === perfil.id
										? '#eff6ff'
										: '#ffffff'}; transition: all 0.2s ease; cursor: pointer; height: 100%; width: 100%;"
									onclick={() => (perfilSeleccionado = perfil.id)}
								>
									<div class="is-flex is-align-items-center mb-1">
										<i class="fa-solid {perfil.icono} mr-2 has-text-link"></i>
										<strong class="is-size-7">{perfil.nombre}</strong>
									</div>
									<span class="tag {perfil.tagColor} is-light is-size-7 is-family-code mb-1">
										{perfil.etiqueta}
									</span>
									<p class="is-size-7 has-text-grey mb-0" style="font-size: 0.72rem !important; line-height: 1.25;">
										{perfil.descripcion}
									</p>
								</button>
							</div>
						{/each}
					</div>
				</div>

				<!-- Selector de Retardo de Red / Transporte (Td) -->
				<div>
					<div class="is-flex is-justify-content-space-between is-align-items-center mb-1">
						<span class="is-size-7 has-text-weight-bold has-text-grey-dark">
							Retardo de Red / Transporte ($T_d$):
						</span>
						<span class="is-size-7 has-text-grey">
							Simula latencia HTTP/TCP o enlace inalámbrico antes del microcontrolador
						</span>
					</div>
					<div class="buttons are-small mb-0">
						<button
							type="button"
							class="button {retardoTdMs === 0 ? 'is-info is-focused has-text-weight-bold' : 'is-light'}"
							onclick={() => (retardoTdMs = 0)}
						>
							<i class="fa-solid fa-bolt mr-1"></i> 0 ms (Bus Local / CAN Directo)
						</button>
						<button
							type="button"
							class="button {retardoTdMs === 200 ? 'is-warning is-focused has-text-weight-bold' : 'is-light'}"
							onclick={() => (retardoTdMs = 200)}
						>
							<i class="fa-solid fa-wifi mr-1"></i> 200 ms (Wi-Fi / Ethernet Industrial)
						</button>
						<button
							type="button"
							class="button {retardoTdMs === 500 ? 'is-danger is-focused has-text-weight-bold' : 'is-light'}"
							onclick={() => (retardoTdMs = 500)}
						>
							<i class="fa-solid fa-satellite-dish mr-1"></i> 500 ms (WAN / Enlace Celular 4G)
						</button>
					</div>
				</div>
			</div>
		</div>

		<!-- Tarjeta 2: Gráfica de Respuesta Temporal en LayerChart -->
		<div class="card concept-card" style="box-shadow: 0 4px 12px rgba(15, 23, 42, 0.06);">
			<header class="card-header px-4 py-3" style="background: #f8fafc; border-bottom: 1px solid #e2e8f0;">
				<div class="is-flex is-align-items-center is-justify-content-space-between is-flex-grow-1" style="flex-wrap: wrap; gap: 0.5rem;">
					<span class="has-text-weight-bold is-size-6">
						<i class="fa-solid fa-chart-line mr-2 has-text-danger"></i>
						Respuesta Temporal al Escalón: Consigna $r(t)$ vs. Planta Real $y(t)$
					</span>
					<!-- Leyenda interactiva de la gráfica -->
					<div class="is-flex is-align-items-center" style="gap: 1rem;">
						<span class="is-size-7 is-flex is-align-items-center">
							<span style="display:inline-block; width:16px; height:3px; background:#2563eb; border-top: 1px dashed #ffffff; margin-right:5px;"></span>
							<strong class="has-text-link">Consigna $r(t)$ (Azul)</strong>
						</span>
						<span class="is-size-7 is-flex is-align-items-center">
							<span style="display:inline-block; width:16px; height:3px; background:#dc2626; margin-right:5px;"></span>
							<strong class="has-text-danger">Rotor Real $y(t)$ (Roja)</strong>
						</span>
					</div>
				</div>
			</header>

			<div class="card-content p-4">
				<!-- Contenedor LayerChart Oficial según app.css (.layerchart-box) -->
				<div class="layerchart-box" style="height: 290px;">
					<Chart
						data={historial}
						x="t"
						y="rpmReal"
						xScale={scaleLinear()}
						yScale={scaleLinear()}
						yDomain={[0, 3400]}
						padding={{ top: 15, right: 15, bottom: 25, left: 45 }}
					>
						<Svg>
							<Axis
								placement="left"
								label="RPM"
								grid={{ stroke: '#f1f5f9' }}
								rule
							/>
							<Axis
								placement="bottom"
								label="Tiempo (s)"
								grid={{ stroke: '#f8fafc' }}
								rule
							/>
							<!-- Curva 1: Consigna Administrativa r(t) en azul punteado -->
							<Spline
								x="t"
								y="consigna"
								stroke="#2563eb"
								strokeWidth={2}
								strokeDasharray="5 3"
							/>
							<!-- Curva 2: Realimentación Física y(t) en rojo sólido -->
							<Spline
								x="t"
								y="rpmReal"
								stroke="#dc2626"
								strokeWidth={2.6}
							/>
						</Svg>
					</Chart>
				</div>

				<!-- Métricas Transitorias Clásicas del Escalón -->
				<div class="columns is-mobile is-multiline mt-2 mb-0 pt-2" style="border-top: 1px solid #f1f5f9;">
					<div class="column is-4 py-1">
						<span class="is-size-7 has-text-grey">Tiempo de Subida ($t_r$ 90%):</span>
						<strong class="is-size-7 is-family-code is-block has-text-dark">
							{tiempoSubidaS > 0 ? `${tiempoSubidaS} s` : 'Calculando...'}
						</strong>
					</div>
					<div class="column is-4 py-1">
						<span class="is-size-7 has-text-grey">Sobreimpulso medido ($M_p$):</span>
						<strong class="is-size-7 is-family-code is-block {sobreimpulsoPct > 0 ? 'has-text-warning-dark' : 'has-text-success'}">
							{sobreimpulsoPct > 0 ? `+${sobreimpulsoPct} %` : '0.0 % (Crítico)'}
						</strong>
					</div>
					<div class="column is-4 py-1">
						<span class="is-size-7 has-text-grey">Discrepancia Actual:</span>
						<strong class="is-size-7 is-family-code is-block has-text-danger">
							{Math.abs(errorLazo)} RPM
						</strong>
					</div>
				</div>
			</div>
		</div>
	</div>
</div>

<!-- Fundamento Teórico Mecatrónico de Cátedra -->
<div class="card mt-5 mb-5" style="border-radius: 10px; border: 1px solid #cbd5e1;">
	<header class="card-header px-4 py-3" style="background: #f1f5f9;">
		<span class="has-text-weight-bold is-size-6">
			<i class="fa-solid fa-graduation-cap mr-2 has-text-link"></i>
			Contraste Teórico: Tiempo Real Administrativo vs. Dinámica Mecánica de 2do Orden
		</span>
	</header>
	<div class="card-content p-4">
		<div class="columns">
			<div class="column is-6">
				<div class="notification is-info is-light p-3" style="height: 100%; border-left: 4px solid #2563eb;">
					<h4 class="title is-6 mb-2">
						<i class="fa-solid fa-desktop mr-1"></i> Tiempo Real Administrativo (&lt; 1 ms)
					</h4>
					<p class="is-size-7 mb-2">
						El operador desliza el potenciómetro web en la interfaz. El enlace reactivo <code>bind:value</code> muta la variable en memoria RAM inmediatamente. Para el DOM del navegador, la consigna ya cambió en microsegundos y la aguja azul se posiciona sin demora.
					</p>
					<div class="p-2 has-background-white" style="border-radius: 4px; font-family: monospace; font-size: 0.78rem;">
						r(t) = input.value &nbsp;// Instantáneo en el hilo de JavaScript
					</div>
				</div>
			</div>

			<div class="column is-6">
				<div class="notification is-danger is-light p-3" style="height: 100%; border-left: 4px solid #dc2626;">
					<h4 class="title is-6 mb-2">
						<i class="fa-solid fa-gears mr-1"></i> Tiempo Real Físico (&tau; = 0.35 a 1.6 s)
					</h4>
					<p class="is-size-7 mb-2">
						El actuador electromecánico no puede cambiar su velocidad angular instantáneamente sin requerir una potencia infinita ($P = \tau \cdot \omega \to \infty$). Su respuesta está gobernada por la 2da Ley de Newton rotacional y la ecuación de segundo orden:
					</p>
					<div class="p-2 has-background-white" style="border-radius: 4px; font-family: monospace; font-size: 0.78rem;">
						d²y/dt² + 2·ζ·ωₙ·(dy/dt) + ωₙ²·y = ωₙ²·u(t - T_d)
					</div>
				</div>
			</div>
		</div>
	</div>
</div>

<!-- Visor de Código Fuente Pedagógico con CodeViewer -->
<CodeViewer
	titulo="Código Fuente — Proyecto 3: El Eco Visual (Svelte 5 Runes)"
	archivos={[
		{
			nombre: 'TachometerSvg.svelte',
			descripcion: 'Instrumento circular SVG vectorial con doble aguja desacoplada: aguja azul instantánea (bind:value) vs. aguja roja con amortiguación CSS y sector de discrepancia angular e(t).',
			codigo: codigoTachometer
		},
		{
			nombre: 'proyecto-3-eco/+page.svelte',
			descripcion: 'Lazo físico a 40 Hz resolviendo la EDO de 2do orden, simulación de retardo de transporte T_d, búfer superficial $state.raw y graficado en tiempo real con LayerChart.',
			codigo: codigoPagina
		}
	]}
/>
