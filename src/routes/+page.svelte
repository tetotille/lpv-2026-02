<script>
	let { data } = $props();

	const proyectosTiempoReal = [
		{
			id: 1,
			codigo: 'PROYECTO 01',
			titulo: 'El Banco de Estrés',
			subtitulo: 'Límite Físico (kHz) vs. Límite de Renderizado (60 fps)',
			ruta: '/proyecto-1-estres',
			icono: 'fa-gauge-high',
			colorBorde: '#dc2626',
			tagClass: 'is-danger is-light',
			btnClass: 'button is-danger is-outlined is-fullwidth',
			fenomeno: 'Frecuencia y Saturación del Hilo Principal',
			mecatronica:
				'Muestreo de acelerómetro MPU6050 / Encoder a 100–1000 Hz frente a la tasa de refresco del monitor (16.67 ms).',
			runes: ['$state vs $state.raw', 'Web Worker', 'requestAnimationFrame', 'LayerChart 60fps']
		},
		{
			id: 2,
			codigo: 'PROYECTO 02',
			titulo: 'El Semáforo de Latencia y Jitter',
			subtitulo: 'Determinismo Físico vs. Latencia Estadística TCP/IP (FastAPI SSE)',
			ruta: '/proyecto-2-jitter',
			icono: 'fa-traffic-light',
			colorBorde: '#d97706',
			tagClass: 'is-warning is-light',
			btnClass: 'button is-warning is-outlined is-fullwidth',
			fenomeno: 'Ausencia de Determinismo y Dato Congelado',
			mecatronica:
				'Detección de enlaces degradados (150–800 ms) y pérdida de sincronización (> 800 ms) desde FastAPI (/api/jitter/stream).',
			runes: ['$derived.by', '$effect con cleanup', 'FastAPI SSE :8007', 'Umbrales LayerChart']
		},
		{
			id: 3,
			codigo: 'PROYECTO 03',
			titulo: 'El Eco Visual',
			subtitulo: 'Consigna Administrativa vs. Realimentación Física con Inercia',
			ruta: '/proyecto-3-eco',
			icono: 'fa-compass-drafting',
			colorBorde: '#2563eb',
			tagClass: 'is-info is-light',
			btnClass: 'button is-info is-outlined is-fullwidth',
			fenomeno: 'Inercia Mecánica y Lazo de Control Cerrado',
			mecatronica:
				'Discrepancia temporal entre el Setpoint del operador y la aceleración real de un rotor con masa inercial.',
			runes: ['bind:value', 'Tacómetro SVG Doble Aguja', 'Planta 2do Orden', 'Curva Step Response']
		},
		{
			id: 4,
			codigo: 'PROYECTO 04',
			titulo: 'El Dashboard SCADA Completo',
			subtitulo: 'Arquitectura BFF SvelteKit + FastAPI, Rutas Dinámicas y Paro de Planta',
			ruta: '/proyecto-4-scada',
			icono: 'fa-industry',
			colorBorde: '#16a34a',
			tagClass: 'is-success is-light',
			btnClass: 'button is-success is-outlined is-fullwidth',
			fenomeno: 'Supervisión Distribuida y Seguridad Funcional',
			mecatronica:
				'Carga SSR desde FastAPI (/api/sensores), telemetría SSE, calibración y Paro Web vs. Relé Categoría 4.',
			runes: ['SSR load()', '/sensores/[id]', '$props() + {#snippet}', 'use:autoScroll + use:enhance']
		}
	];

	const proyectosAdministrativos = [
		{
			id: 5,
			codigo: 'PROYECTO 05 (ADMIN 1)',
			titulo: 'OEE y Lucro Cesante en Millones de ₲',
			subtitulo: 'Traducción de Micro-Paradas Mecatrónicas a Pérdidas Financieras por Turno',
			ruta: '/admin-1-oee',
			icono: 'fa-chart-pie',
			colorBorde: '#e11d48',
			tagClass: 'is-danger is-light',
			btnClass: 'button is-danger is-fullwidth',
			endpoint: 'GET/POST /api/admin/oee',
			mecatronica:
				'Cruce de Disponibilidad × Rendimiento × Calidad con el costo por minuto de línea caída (₲ 1.450.000/min). Sin streaming: cortes SSR deterministas para toma de decisiones.',
			runes: ['SSR load(url.searchParams)', 'FastAPI /api/admin/oee', 'Form Action ?/registrarParo', 'LayerChart']
		},
		{
			id: 6,
			codigo: 'PROYECTO 06 (ADMIN 2)',
			titulo: 'Auditoría Energética Pliego ANDE (₲)',
			subtitulo: 'Horario Punta (18–22 hs), Multa por Factor de Potencia (cos φ < 0.92) y ROI',
			ruta: '/admin-2-energia-ande',
			icono: 'fa-plug-circle-bolt',
			colorBorde: '#d97706',
			tagClass: 'is-warning is-light',
			btnClass: 'button is-warning is-fullwidth has-text-dark',
			endpoint: 'GET/POST /api/admin/energia-ande',
			mecatronica:
				'Liquidación industrial en Media Tensión (23 kV): simulación de instalación de bancos de capacitores y desplazamiento de turnos de molienda/hornos con cálculo de Payback en meses.',
			runes: ['FastAPI /api/admin/energia-ande', 'use:enhance ?/simularTarifa', 'Curva 24h LayerChart', 'Moneda PYG ₲']
		},
		{
			id: 7,
			codigo: 'PROYECTO 07 (ADMIN 3)',
			titulo: 'Matriz CapEx/OpEx y Órdenes de Compra (₲)',
			subtitulo: 'Mantenimiento Predictivo Weibull vs. Falla Catastrófica + Idempotencia HTTP 409',
			ruta: '/admin-3-capex-mantenimiento',
			icono: 'fa-file-signature',
			colorBorde: '#2563eb',
			tagClass: 'is-link is-light',
			btnClass: 'button is-link is-fullwidth',
			endpoint: 'GET/POST /api/admin/capex',
			mecatronica:
				'Autorización de desembolsos de cientos de millones de ₲ con doble confirmación ejecutiva (Bits UI AlertDialog) y protección contra doble cobro mediante idempotency_key.',
			runes: ['FastAPI /api/admin/capex', 'Idempotency Key (HTTP 409)', 'Bits UI AlertDialog', 'Curva Weibull LayerChart']
		},
		{
			id: 8,
			codigo: 'PROYECTO 08 (ADMIN 4)',
			titulo: 'Conciliación de Lotes MES vs. ERP (₲)',
			subtitulo: 'Balance de Masa (Caudalímetros/Celdas de Carga) vs. Contabilidad y Mermas',
			ruta: '/admin-4-conciliacion-lotes',
			icono: 'fa-scale-unbalanced',
			colorBorde: '#0d9488',
			tagClass: 'is-primary is-light',
			btnClass: 'button is-primary is-fullwidth',
			endpoint: 'GET/POST /api/admin/conciliacion-lotes',
			mecatronica:
				'Auditoría de lotes cerrados para detectar descalibraciones metrológicas o fugas que superan el 1.5% de tolerancia contable, emitiendo dictámenes firmados en FastAPI.',
			runes: ['FastAPI /api/admin/conciliacion-lotes', 'Form Action ?/emitirDictamen', 'Rule 1.5% LayerChart', 'Auditoría PYG']
		}
	];
</script>

<svelte:head>
	<title>Clase 7: Tiempo Real vs. Dashboards Administrativos en ₲ — FIUNA</title>
</svelte:head>

<!-- Hero Principal -->
<section class="hero is-medium mb-6 hero-scada">
	<div class="hero-body py-6">
		<div class="columns is-vcentered">
			<div class="column is-8">
				<span class="tag is-warning has-text-weight-bold mb-3 is-medium">
					<i class="fa-solid fa-microchip mr-2"></i> Lenguajes de Programación Visual · FIUNA
				</span>
				<h1 class="title is-1 has-text-white mb-3">
					De los Microsegundos Físicos a las Decisiones de Millones de Guaraníes (₲)
				</h1>
				<p class="subtitle is-5 has-text-white-bis">
					Suite completa de <strong>8 laboratorios interactivos</strong> conectados a
					<strong>FastAPI (`:8007`)</strong>: comprende cuándo desacoplar flujos de alta frecuencia a
					60 fps (<strong>Parte I</strong>) y cuándo exigir snapshots deterministas, exactitud
					contable e idempotencia transaccional sin tiempo real (<strong>Parte II</strong>).
				</p>
				<div class="buttons mt-4">
					<a href="#parte-1" class="button is-warning is-medium has-text-weight-bold">
						<i class="fa-solid fa-bolt mr-2"></i> Parte I: Tiempo Real (Labs 1–4)
					</a>
					<a href="#parte-2" class="button is-success is-medium has-text-weight-bold">
						<i class="fa-solid fa-sack-dollar mr-2"></i> Parte II: Dashboards en ₲ (Labs 5–8)
					</a>
				</div>
			</div>

			<div class="column is-4">
				<div class="box p-4" style="background: rgba(255,255,255,0.96); border-radius: 12px;">
					<h3 class="title is-6 mb-3">
						<i class="fa-solid fa-layer-group mr-1 has-text-link"></i> Las 3 Fronteras Temporales en Planta
					</h3>
					<div class="mb-2 p-2" style="background:#fef2f2; border-radius:8px; border-left:4px solid #dc2626;">
						<p class="is-size-7 has-text-weight-bold">1. Tiempo Real Físico (kHz / &mu;s)</p>
						<p class="is-size-7">Lazos PID en ESP32/STM32 y relés cableados Categoría 4.</p>
					</div>
					<div class="mb-2 p-2" style="background:#eff6ff; border-radius:8px; border-left:4px solid #2563eb;">
						<p class="is-size-7 has-text-weight-bold">2. Supervisión Operativa (60 fps / SSE)</p>
						<p class="is-size-7">SCADA en vivo (Labs 1–4): baja latencia visual y detección de jitter.</p>
					</div>
					<div class="p-2" style="background:#f0fdf4; border-radius:8px; border-left:4px solid #16a34a;">
						<p class="is-size-7 has-text-weight-bold">3. Decisión Ejecutiva en Millones de ₲ (Batch / SSR)</p>
						<p class="is-size-7">
							Gerencia/ERP (Labs 5–8): datos estáticos verificados, simulación de ROI e idempotencia.
						</p>
					</div>
				</div>
			</div>
		</div>
	</div>
</section>

<!-- SECCIÓN PARTE II: 4 NUEVOS LABORATORIOS ADMINISTRATIVOS EN MILLONES DE GUARANÍES -->
<div id="parte-2" class="mb-6">
	<div class="notification is-success is-light mb-4" style="border-left: 5px solid #16a34a;">
		<div class="level is-mobile" style="flex-wrap: wrap;">
			<div class="level-left">
				<div>
					<span class="tag is-success has-text-weight-bold mb-1">NUEVO · PARTE II</span>
					<h2 class="title is-3 mb-1">
						Dashboards Administrativos de Millones de Guaraníes (Proyectos 5 al 8)
					</h2>
					<p class="is-size-6">
						Operaciones que <strong>NO requieren ni deben usar streaming en tiempo real</strong>:
						consultan snapshots consistentes y ejecutan transacciones auditadas en
						<strong>FastAPI (`http://localhost:8007/api/admin/*`)</strong>.
					</p>
				</div>
			</div>
		</div>
	</div>

	<div class="columns is-multiline">
		{#each proyectosAdministrativos as p (p.id)}
			<div class="column is-6">
				<div class="card concept-card" style="border-top: 5px solid {p.colorBorde};">
					<div class="card-content">
						<div class="level is-mobile mb-2">
							<div class="level-left">
								<span class="tag {p.tagClass} is-medium has-text-weight-bold">
									<i class="fa-solid {p.icono} mr-2"></i> {p.codigo}
								</span>
							</div>
							<div class="level-right">
								<span class="tag is-dark is-family-code">{p.endpoint}</span>
							</div>
						</div>

						<h3 class="title is-4 mb-1">{p.titulo}</h3>
						<p class="is-size-6 has-text-weight-semibold has-text-link mb-3">{p.subtitulo}</p>
						<p class="is-size-6 mb-4">{p.mecatronica}</p>

						<div class="tags">
							{#each p.runes as rune (rune)}
								<span class="tag is-rounded is-light is-family-code">{rune}</span>
							{/each}
						</div>
					</div>
					<footer class="card-footer px-4 pb-4 pt-0" style="border-top: none;">
						<a href={p.ruta} class="{p.btnClass} has-text-weight-bold">
							<span>Abrir Dashboard Ejecutivo en ₲</span>
							<i class="fa-solid fa-arrow-right ml-2"></i>
						</a>
					</footer>
				</div>
			</div>
		{/each}
	</div>
</div>

<!-- SECCIÓN PARTE I: 4 PROYECTOS DE TIEMPO REAL OPERATIVO -->
<div id="parte-1" class="mb-6">
	<h2 class="title is-3 mb-1">
		Parte I: Frontera entre Tiempo Real Físico y Supervisión Web (Proyectos 1 al 4)
	</h2>
	<p class="subtitle is-6 has-text-grey mb-4">
		Laboratorios enfocados en frecuencias de muestreo (kHz), refresco a 60 fps, jitter de red e inercia mecánica:
	</p>

	<div class="columns is-multiline">
		{#each proyectosTiempoReal as p (p.id)}
			<div class="column is-6">
				<div class="card concept-card" style="border-top: 5px solid {p.colorBorde};">
					<div class="card-content">
						<div class="level is-mobile mb-2">
							<div class="level-left">
								<span class="tag {p.tagClass} is-medium has-text-weight-bold">
									<i class="fa-solid {p.icono} mr-2"></i> {p.codigo}
								</span>
							</div>
							<div class="level-right">
								<span class="tag is-light is-family-code">{p.fenomeno}</span>
							</div>
						</div>

						<h3 class="title is-4 mb-1">{p.titulo}</h3>
						<p class="is-size-6 has-text-weight-semibold has-text-link mb-3">{p.subtitulo}</p>
						<p class="is-size-6 mb-4">{p.mecatronica}</p>

						<div class="tags">
							{#each p.runes as rune (rune)}
								<span class="tag is-rounded is-light is-family-code">{rune}</span>
							{/each}
						</div>
					</div>
					<footer class="card-footer px-4 pb-4 pt-0" style="border-top: none;">
						<a href={p.ruta} class="{p.btnClass} has-text-weight-bold">
							<span>Abrir Laboratorio de Tiempo Real</span>
							<i class="fa-solid fa-arrow-right ml-2"></i>
						</a>
					</footer>
				</div>
			</div>
		{/each}
	</div>
</div>

<style>
	.hero-scada {
		border-radius: 14px;
		background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 55%, #065f46 100%);
		box-shadow: 0 12px 28px -6px rgba(15, 23, 42, 0.35);
	}
</style>
