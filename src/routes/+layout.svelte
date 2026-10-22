<script>
	import '../app.css';
	import { page } from '$app/state';
	import { invalidateAll } from '$app/navigation';

	let { data, children } = $props();

	let menuActivo = $state(false);
	let relojCliente = $state('--:--:--.---');
	let verificandoBackend = $state(false);

	const esRutaConFastApi = $derived(
		page.url.pathname.startsWith('/proyecto-2') ||
			page.url.pathname.startsWith('/proyecto-4') ||
			page.url.pathname.startsWith('/admin-')
	);

	// Reloj de supervisión administrativa en el cliente con limpieza automática
	$effect(() => {
		const actualizarReloj = () => {
			const ahora = new Date();
			const hh = String(ahora.getHours()).padStart(2, '0');
			const mm = String(ahora.getMinutes()).padStart(2, '0');
			const ss = String(ahora.getSeconds()).padStart(2, '0');
			const ms = String(ahora.getMilliseconds()).padStart(3, '0');
			relojCliente = `${hh}:${mm}:${ss}.${ms}`;
		};
		actualizarReloj();
		const timer = setInterval(actualizarReloj, 97);
		return () => clearInterval(timer);
	});

	async function reintentarFastApi() {
		verificandoBackend = true;
		try {
			await invalidateAll();
		} finally {
			verificandoBackend = false;
		}
	}
</script>

<div class="site-container">
	<!-- Navbar Principal Industrial con ambas Partes (Tiempo Real vs. Dashboards Administrativos en ₲) -->
	<nav
		class="navbar is-white has-shadow"
		aria-label="main navigation"
		style="border-bottom: 1px solid #e2e8f0;"
	>
		<div class="container">
			<div class="navbar-brand">
				<a class="navbar-item has-text-weight-bold is-size-6" href="/">
					<span class="tag is-dark mr-2">
						<i class="fa-solid fa-microchip has-text-warning mr-1"></i> LPV
					</span>
					<span>Clase 7: Mecatrónica &amp; Gestión</span>
				</a>

				<button
					type="button"
					class="navbar-burger {menuActivo ? 'is-active' : ''}"
					aria-label="menu"
					aria-expanded={menuActivo}
					onclick={() => (menuActivo = !menuActivo)}
				>
					<span aria-hidden="true"></span>
					<span aria-hidden="true"></span>
					<span aria-hidden="true"></span>
					<span aria-hidden="true"></span>
				</button>
			</div>

			<div class="navbar-menu {menuActivo ? 'is-active' : ''}">
				<div class="navbar-start">
					<a
						class="navbar-item {page.url.pathname === '/'
							? 'is-active has-text-link has-text-weight-bold'
							: ''}"
						href="/"
					>
						<i class="fa-solid fa-compass mr-1"></i> Portal (8 Labs)
					</a>

					<!-- Dropdown Parte I: Tiempo Real Operativo -->
					<div class="navbar-item has-dropdown is-hoverable">
						<a
							class="navbar-link {page.url.pathname.startsWith('/proyecto-')
								? 'has-text-link has-text-weight-bold'
								: ''}"
							href="/proyecto-1-estres"
						>
							<i class="fa-solid fa-bolt mr-1 has-text-danger"></i> Parte I: Tiempo Real (1–4)
						</a>
						<div class="navbar-dropdown">
							<a class="navbar-item" href="/proyecto-1-estres">
								<i class="fa-solid fa-gauge-high mr-2 has-text-danger"></i> 1. Banco de Estrés (kHz vs 60fps)
							</a>
							<a class="navbar-item" href="/proyecto-2-jitter">
								<i class="fa-solid fa-traffic-light mr-2 has-text-warning"></i> 2. Semáforo de Red y Jitter
							</a>
							<a class="navbar-item" href="/proyecto-3-eco">
								<i class="fa-solid fa-compass-drafting mr-2 has-text-info"></i> 3. El Eco Visual (Inercia)
							</a>
							<a class="navbar-item" href="/proyecto-4-scada">
								<i class="fa-solid fa-industry mr-2 has-text-success"></i> 4. SCADA Fullstack + Paro
							</a>
						</div>
					</div>

					<!-- Dropdown Parte II: Dashboards Administrativos en Millones de ₲ -->
					<div class="navbar-item has-dropdown is-hoverable">
						<a
							class="navbar-link {page.url.pathname.startsWith('/admin-')
								? 'has-text-link has-text-weight-bold'
								: ''}"
							href="/admin-1-oee"
						>
							<i class="fa-solid fa-sack-dollar mr-1 has-text-success"></i> Parte II: Gerencia en ₲ (5–8)
						</a>
						<div class="navbar-dropdown">
							<a class="navbar-item" href="/admin-1-oee">
								<i class="fa-solid fa-chart-pie mr-2 has-text-danger"></i> 5. OEE y Lucro Cesante (₲)
							</a>
							<a class="navbar-item" href="/admin-2-energia-ande">
								<i class="fa-solid fa-plug-circle-bolt mr-2 has-text-warning"></i> 6. Auditoría Pliego ANDE (₲)
							</a>
							<a class="navbar-item" href="/admin-3-capex-mantenimiento">
								<i class="fa-solid fa-file-signature mr-2 has-text-link"></i> 7. Matriz CapEx y Órdenes (₲)
							</a>
							<a class="navbar-item" href="/admin-4-conciliacion-lotes">
								<i class="fa-solid fa-scale-unbalanced mr-2 has-text-primary"></i> 8. Conciliación MES vs ERP (₲)
							</a>
						</div>
					</div>
				</div>

				<div class="navbar-end">
					<div class="navbar-item">
						<div class="tags has-addons mb-0">
							<span class="tag is-dark is-family-code">FastAPI :8007</span>
							{#if data.fastapiOnline}
								<span class="tag is-success has-text-weight-bold pulse-green">
									<i class="fa-solid fa-circle-check mr-1"></i> ONLINE
								</span>
							{:else}
								<span class="tag is-danger has-text-weight-bold">
									<i class="fa-solid fa-plug-circle-xmark mr-1"></i> OFFLINE
								</span>
							{/if}
						</div>
					</div>
				</div>
			</div>
		</div>
	</nav>

	<!-- Barra de Telemetría Global (+layout.server.js + Reloj Cliente) -->
	<section
		class="py-2 px-3"
		style="background-color: #f1f5f9; border-bottom: 1px solid #cbd5e1; font-size: 0.8rem;"
	>
		<div class="container">
			<div class="level is-mobile mb-0" style="flex-wrap: wrap; gap: 0.5rem;">
				<div class="level-left" style="flex-wrap: wrap; gap: 0.5rem;">
					<span class="tag is-white" style="border: 1px solid #cbd5e1;">
						<i class="fa-solid fa-clock mr-1 has-text-link"></i>
						<strong>Reloj Cliente:</strong>&nbsp;<code style="border:none; padding:0;"
							>{relojCliente}</code
						>
					</span>
					<span class="tag is-white is-hidden-mobile" style="border: 1px solid #cbd5e1;">
						<i class="fa-solid fa-server mr-1 has-text-primary"></i>
						<strong>SSR Snapshot:</strong>&nbsp;{data.horaServidorSvelteKit}
					</span>
					<span class="tag is-info is-light has-text-weight-semibold is-hidden-mobile">
						Backend Obligatorio: {data.fastapiUrl}
					</span>
				</div>

				<div class="level-right">
					{#if !data.fastapiOnline}
						<button
							type="button"
							class="button is-small is-danger is-light has-text-weight-bold"
							onclick={reintentarFastApi}
							disabled={verificandoBackend}
						>
							<i class="fa-solid fa-rotate mr-1"></i>
							{verificandoBackend ? 'Verificando...' : 'Reintentar conexión FastAPI (:8007)'}
						</button>
					{:else}
						<span class="tag is-success is-light has-text-weight-semibold">
							<i class="fa-solid fa-satellite-dish mr-1"></i>
							Planta: {data.fastapiEstado?.estado_planta || 'EN_MARCHA'}
						</span>
					{/if}
				</div>
			</div>
		</div>
	</section>

	{#if !data.fastapiOnline && esRutaConFastApi}
		<div class="container px-3 mt-4">
			<div class="notification is-danger is-light" style="border-left: 5px solid #dc2626;">
				<div class="columns is-vcentered">
					<div class="column is-9">
						<p class="has-text-weight-bold is-size-6 mb-1">
							<i class="fa-solid fa-triangle-exclamation mr-1"></i>
							Servidor FastAPI Requerido Obligatoriamente ({data.fastapiUrl})
						</p>
						<p class="is-size-7 mb-2">
							Esta ruta obtiene <strong>el 100% de sus datos desde FastAPI</strong> (sin datos simulados
							locales). Levanta el backend en una terminal:
						</p>
						<pre
							class="p-2 is-size-7"
							style="background:#0f172a; color:#f8fafc; border-radius:6px;"><code>npm run backend   # o: cd backend_fastapi && ~/.venv/bin/uvicorn main:app --reload --port 8007</code></pre>
					</div>
					<div class="column is-3 has-text-right-tablet">
						<button
							type="button"
							class="button is-danger has-text-weight-bold"
							onclick={reintentarFastApi}
						>
							<i class="fa-solid fa-plug mr-1"></i> Reintentar Enlace
						</button>
					</div>
				</div>
			</div>
		</div>
	{/if}

	<main class="main-content py-5">
		<div class="container px-3">
			{@render children()}
		</div>
	</main>

	<footer class="footer py-5 mt-6" style="background-color: #ffffff; border-top: 1px solid #e2e8f0;">
		<div class="content has-text-centered is-size-7">
			<p>
				<strong>Lenguajes de Programación Visual — Facultad de Ingeniería (UNA)</strong> · Clase 7:
				Supervisión en Tiempo Real (Proyectos 1–4) y Dashboards Administrativos en Millones de ₲ (Proyectos 5–8).
			</p>
			<p class="has-text-grey">
				Desarrollado con <strong>SvelteKit + Svelte 5 Runes</strong>, <strong>Bulma CSS</strong>,
				<strong>LayerChart</strong>, <strong>Bits UI</strong> y <strong>FastAPI (:8007)</strong>.
			</p>
		</div>
	</footer>
</div>

<style>
	.site-container {
		display: flex;
		flex-direction: column;
		min-height: 100vh;
	}
	.main-content {
		flex: 1;
	}
</style>
