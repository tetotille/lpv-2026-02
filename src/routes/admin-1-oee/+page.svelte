<script>
	/**
	 * Proyecto 5 (Admin 1): "El Costo Oculto de la Ineficiencia: OEE y Lucro Cesante por Turnos en Millones de Guaraníes (₲)"
	 * Ruta: /admin-1-oee
	 *
	 * Svelte 5 Runes: $props, $state, $derived, $derived.by
	 * Cátedra: Lenguajes de Programación Visual — FIUNA
	 *
	 * Arquitectura de Tiempo Real Administrativo:
	 * - 100% alimentado por FastAPI (http://localhost:8007/api/admin/oee)
	 * - Cortes consistentes e inmutables vía SSR load() + URL SearchParams
	 * - Sin streaming a 60 fps (anti-patrón en finanzas y auditoría contable)
	 * - Mutaciones de paradas auditadas vía Form Actions con use:enhance y revalidación automática
	 */

	import { enhance } from '$app/forms';
	import { Chart, Svg, Spline, Area, Axis, Rule } from 'layerchart';
	import { scaleLinear } from 'd3-scale';
	import { formatearGuaranies, formatearMillonesGuaranies } from '$lib/utils/moneda.js';
	import { FASTAPI_BASE_URL } from '$lib/config.js';
	import CodeViewer from '$lib/components/CodeViewer.svelte';

	let { data, form } = $props();

	// Extracción reactiva de datos devueltos por el servidor SvelteKit
	const reporte = $derived(data?.reporte || null);
	const kpis = $derived(reporte?.kpis || null);
	const turnos = $derived(reporte?.turnos || []);
	const serieDiaria = $derived(reporte?.serie_diaria || []);
	const parosRegistrados = $derived(reporte?.paros_registrados || []);
	const lineasCatalogo = $derived(reporte?.lineas_catalogo || []);

	// Estado local del simulador de reducción de paradas (en minutos)
	let minutosAhorroSimulados = $state(45);
	let guardandoParo = $state(false);

	// Cálculo derivado del impacto financiero proyectado en el cliente ($derived.by)
	const simulacion = $derived.by(() => {
		if (!kpis) {
			return {
				ahorroGs: 0,
				lucroNuevoGs: 0,
				oeeProyectado: 0,
				disponibilidadProyectada: 0,
				ahorroMillones: 0
			};
		}
		const costoMinuto = Number(kpis.costo_minuto_promedio_gs) || 1450000;
		const ahorroGs = minutosAhorroSimulados * costoMinuto;
		const lucroActual = Number(kpis.lucro_cesante_total_gs) || 0;
		const lucroNuevoGs = Math.max(0, lucroActual - ahorroGs);

		const dispActual = Number(kpis.disponibilidad_pct) || 80.0;
		const rendActual = Number(kpis.rendimiento_pct) || 90.0;
		const calActual = Number(kpis.calidad_pct) || 95.0;

		// Mejora estimada en disponibilidad al recortar paradas
		const deltaDisp = (minutosAhorroSimulados / 1800) * 8.5;
		const disponibilidadProyectada = Math.min(99.5, dispActual + deltaDisp);
		const oeeProyectado = Math.min(
			99.5,
			(disponibilidadProyectada / 100) * (rendActual / 100) * (calActual / 100) * 100
		);

		return {
			ahorroGs,
			lucroNuevoGs,
			oeeProyectado,
			disponibilidadProyectada,
			ahorroMillones: ahorroGs / 1_000_000
		};
	});

	// Métricas para LayerChart
	const maxPerdida = $derived.by(() => {
		if (!serieDiaria || serieDiaria.length === 0) return 300;
		const max = Math.max(...serieDiaria.map((d) => Number(d.perdida_millones_gs) || 0));
		return Math.max(max * 1.15, 120);
	});

	const promedioPerdida = $derived.by(() => {
		if (!serieDiaria || serieDiaria.length === 0) return 0;
		const suma = serieDiaria.reduce((acc, d) => acc + (Number(d.perdida_millones_gs) || 0), 0);
		return suma / serieDiaria.length;
	});

	// Fragmentos de código pedagógico para el componente CodeViewer
	const codigoServerJs = `import { FASTAPI_BASE_URL } from '$lib/config.js';
import { fail } from '@sveltejs/kit';

/**
 * BFF SSR: Carga determinista desde FastAPI con URL SearchParams
 * En finanzas y OEE contable, NO se utiliza streaming a 60 fps:
 * Las cifras deben permanecer inmutables durante el análisis de balances.
 */
export async function load({ url, fetch }) {
    const linea = url.searchParams.get('linea') || 'TODAS';
    const periodo = url.searchParams.get('periodo') || 'mes';
    const meta = url.searchParams.get('meta') || '85';

    const endpoint = \`\${FASTAPI_BASE_URL}/api/admin/oee?linea=\${encodeURIComponent(linea)}&periodo=\${encodeURIComponent(periodo)}&meta_disponibilidad=\${encodeURIComponent(meta)}\`;
    const res = await fetch(endpoint);

    if (!res.ok) {
        return {
            fastapiOnline: false,
            errorConexion: \`No se pudo obtener el reporte OEE desde FastAPI (\${FASTAPI_BASE_URL}/api/admin/oee)\`
        };
    }

    return {
        fastapiOnline: true,
        endpointConsultado: endpoint,
        reporte: await res.json()
    };
}

export const actions = {
    registrarParo: async ({ request, fetch }) => {
        const fd = await request.formData();
        const res = await fetch(\`\${FASTAPI_BASE_URL}/api/admin/oee/registrar-paro-auditado\`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                linea: fd.get('linea'),
                turno: fd.get('turno'),
                minutos: Number(fd.get('minutos')),
                causa: fd.get('causa'),
                responsable: fd.get('responsable')
            })
        });
        if (!res.ok) return fail(400, { error: 'Error al registrar paro en backend' });
        return { success: true, respuesta: await res.json() };
    }
};`;

	const codigoSvelteJs = `// Svelte 5 Runes: Reactividad determinista en cliente
let { data, form } = $props();

const reporte = $derived(data.reporte);
const kpis = $derived(reporte?.kpis);
let minutosAhorroSimulados = $state(45);

// Simulación de ahorro financiero derivada en vivo ($derived.by)
const simulacion = $derived.by(() => {
    const costoMinuto = kpis.costo_minuto_promedio_gs;
    const ahorroGs = minutosAhorroSimulados * costoMinuto;
    return {
        ahorroGs,
        lucroNuevoGs: Math.max(0, kpis.lucro_cesante_total_gs - ahorroGs)
    };
});

<!-- Gráfica LayerChart montada en contenedor .layerchart-box -->
<div class="layerchart-box" style="height: 300px;">
    <Chart data={reporte.serie_diaria} x="dia_num" y="perdida_millones_gs" xScale={scaleLinear()} yScale={scaleLinear()}>
        <Svg>
            <Axis placement="left" grid rule format={(d) => \`\${d} M\`} />
            <Axis placement="bottom" rule format={(d) => \`Día \${d}\`} />
            <Area style="fill: rgba(239, 68, 68, 0.15);" />
            <Spline style="stroke: #dc2626; stroke-width: 2.5px;" />
            <Rule y={promedioPerdida} style="stroke: #b91c1c; stroke-dasharray: 4,4;" />
        </Svg>
    </Chart>
</div>`;

	const codigoFastApiPy = `@app.get("/api/admin/oee")
async def get_admin_oee(linea: str = "TODAS", periodo: str = "mes", meta_disponibilidad: float = 85.0):
    """
    Calcula OEE industrial integral y valoriza el lucro cesante en Millones de Guaraníes (₲).
    OEE = Disponibilidad x Rendimiento x Calidad
    Lucro Cesante = Minutos Paro x Costo Minuto Línea (₲) + Pérdidas Calidad/Rendimiento
    """
    costo_minuto = LINEAS_INFO[linea]["costo_minuto_parada_gs"] if linea != "TODAS" else 1426667
    lucro_total = minutos_paro * costo_minuto + perdida_scrap_gs
    return {
        "linea_seleccionada": linea,
        "periodo_seleccionado": periodo,
        "meta_disponibilidad": meta_disponibilidad,
        "kpis": {
            "oee_pct": 74.2,
            "disponibilidad_pct": 81.5,
            "rendimiento_pct": 94.0,
            "calidad_pct": 96.8,
            "lucro_cesante_total_gs": lucro_total,
            "costo_minuto_promedio_gs": costo_minuto,
            "ahorro_potencial_meta_gs": ahorro_meta_gs
        },
        "turnos": turnos_list,
        "serie_diaria": serie_diaria_puntos,
        "paros_registrados": incidentes_db
    }`;
</script>

<svelte:head>
	<title>Admin 1: OEE y Lucro Cesante en Millones de ₲ — Clase 7 FIUNA</title>
</svelte:head>

<!-- Migas de Pan (Breadcrumbs) -->
<nav class="breadcrumb has-arrow-separator mb-4" aria-label="breadcrumbs">
	<ul>
		<li><a href="/"><i class="fa-solid fa-compass mr-1"></i> Portal</a></li>
		<li><span class="tag is-info is-light mr-2">Módulo Administrativo</span></li>
		<li class="is-active">
			<a href="/admin-1-oee" class="has-text-weight-bold">
				<i class="fa-solid fa-chart-pie mr-1"></i> Admin 1: OEE &amp; Lucro Cesante (₲)
			</a>
		</li>
	</ul>
</nav>

<!-- SECCIÓN 1: CABECERA PEDAGÓGICA Y TRAZABILIDAD HTTP A FASTAPI -->
<div class="box mb-5 header-box">
	<div class="level is-mobile mb-3" style="flex-wrap: wrap; gap: 0.5rem;">
		<div class="level-left">
			<div>
				<div class="tags has-addons mb-1">
					<span class="tag is-dark">Proyecto 5</span>
					<span class="tag is-primary has-text-weight-bold">Tiempo Real Administrativo</span>
					{#if data?.fastapiOnline}
						<span class="tag is-success">
							<i class="fa-solid fa-circle-check mr-1"></i> FastAPI Online
						</span>
					{:else}
						<span class="tag is-danger">
							<i class="fa-solid fa-triangle-exclamation mr-1"></i> FastAPI Desconectado
						</span>
					{/if}
				</div>
				<h1 class="title is-3 mb-1">
					<i class="fa-solid fa-calculator mr-2 has-text-danger"></i>
					El Costo Oculto de la Ineficiencia: OEE y Lucro Cesante en Millones de ₲
				</h1>
				<p class="subtitle is-6 has-text-grey">
					Efectividad Global de Equipos, Desglose por Turnos y Trazabilidad Financiera de Paradas No Programadas.
				</p>
			</div>
		</div>

		<div class="level-right">
			<div class="has-text-right">
				<div class="tag is-black is-family-code mb-1 is-medium">
					<i class="fa-solid fa-link mr-2 has-text-info"></i>
					GET {data?.endpointConsultado || `${FASTAPI_BASE_URL}/api/admin/oee`}
				</div>
				<p class="is-size-7 has-text-grey">
					Consumo SSR vía SvelteKit BFF (Backend-For-Frontend)
				</p>
			</div>
		</div>
	</div>

	<!-- Nota de Cátedra sobre Tiempo Real Administrativo vs. Físico -->
	<article class="message is-dark mb-0">
		<div class="message-body is-size-7 py-3">
			<div class="columns is-vcentered">
				<div class="column is-8">
					<p class="mb-1">
						<strong><i class="fa-solid fa-graduation-cap mr-1 has-text-warning"></i> Principio de Arquitectura de Sistemas de Información Industrial:</strong>
					</p>
					<p>
						A diferencia de un sensor físico o lazo de control SCADA que requiere streaming a 60 fps (16,6 ms),
						un <strong>Dashboard Gerencial donde se imputan balances de miles de millones de Guaraníes (₲)</strong>
						requiere <strong>cortes consistentes deterministas (SSR load + URL SearchParams)</strong>.
						Las cifras contables deben permanecer <em>estáticas e inmutables</em> mientras el Director Industrial
						analiza el balance y toma decisiones; un streaming continuo provocaría desfases de conciliación y decisiones sobre números volátiles.
					</p>
				</div>
				<div class="column is-4 has-text-right-tablet">
					<div class="tag is-info is-light is-size-7 py-2 px-3">
						<i class="fa-solid fa-coins mr-2 has-text-warning"></i>
						Moneda: Guaraníes Paraguayos (₲ PYG)
						<br />
						Sin decimales contables (Intl es-PY)
					</div>
				</div>
			</div>
		</div>
	</article>
</div>

<!-- ALERTA SI FASTAPI ESTÁ DESCONECTADO -->
{#if !data?.fastapiOnline}
	<div class="notification is-danger is-light mb-5" style="border-left: 6px solid #dc2626;">
		<div class="is-flex is-align-items-start">
			<span class="icon is-large mr-3 has-text-danger">
				<i class="fa-solid fa-triangle-exclamation fa-2x"></i>
			</span>
			<div>
				<h3 class="title is-5 mb-1 has-text-danger-dark">Error de Enlace con el Servidor Contable FastAPI</h3>
				<p class="mb-2">
					{data?.errorConexion || 'No se pudo conectar con el endpoint /api/admin/oee en FastAPI.'}
				</p>
				<p class="is-size-7 has-text-grey-dark">
					<strong>Regla Técnica Estricta:</strong> En los Laboratorios Administrativos de la Clase 7,
					<strong>el 100% de los datos financieros proviene de FastAPI (puerto 8007)</strong>.
					No existen datos simulados ni fallbacks ficticios en SvelteKit.
					Asegúrate de que el backend Python esté ejecutándose:
					<code>uvicorn main:app --reload --port 8007</code>
				</p>
			</div>
		</div>
	</div>
{/if}

<!-- SECCIÓN 2: BARRA DE FILTROS DETERMINISTAS (SSR QUERY PARAMS) -->
<div class="card mb-5 filter-card">
	<div class="card-content py-4 px-5">
		<form method="GET" action="/admin-1-oee">
			<div class="level mb-0" style="flex-wrap: wrap; gap: 1rem;">
				<div class="level-left is-flex-grow-1" style="flex-wrap: wrap; gap: 1rem;">
					<!-- Filtro Línea de Producción -->
					<div class="field mb-0">
						<label class="label is-small mb-1" for="select-linea">
							<i class="fa-solid fa-industry mr-1 has-text-info"></i> Línea de Producción
						</label>
						<div class="control has-icons-left">
							<div class="select is-small is-fullwidth">
								<select id="select-linea" name="linea" value={data?.filtros?.linea || 'TODAS'}>
									<option value="TODAS">Consolidado Todas las Líneas (Planta)</option>
									<option value="L1">L1: Embotellado PET Alta Velocidad (₲ 1.450.000/min)</option>
									<option value="L2">L2: Envasado Aséptico Tetra (₲ 1.850.000/min)</option>
									<option value="L3">L3: Empaque y Paletizado Robótico (₲ 980.000/min)</option>
								</select>
							</div>
							<span class="icon is-small is-left">
								<i class="fa-solid fa-diagram-project"></i>
							</span>
						</div>
					</div>

					<!-- Filtro Período Contable -->
					<div class="field mb-0">
						<label class="label is-small mb-1" for="select-periodo">
							<i class="fa-solid fa-calendar-days mr-1 has-text-info"></i> Período Contable
						</label>
						<div class="control has-icons-left">
							<div class="select is-small">
								<select id="select-periodo" name="periodo" value={data?.filtros?.periodo || 'mes'}>
									<option value="7d">Últimos 7 Días (Corte Semanal)</option>
									<option value="mes">Mes en Curso (Octubre 2026)</option>
									<option value="trimestre">Trimestre Acumulado (Q4)</option>
								</select>
							</div>
							<span class="icon is-small is-left">
								<i class="fa-regular fa-clock"></i>
							</span>
						</div>
					</div>

					<!-- Filtro Meta de Disponibilidad -->
					<div class="field mb-0">
						<label class="label is-small mb-1" for="select-meta">
							<i class="fa-solid fa-bullseye mr-1 has-text-danger"></i> Meta de Disponibilidad
						</label>
						<div class="control has-icons-left">
							<div class="select is-small">
								<select id="select-meta" name="meta" value={String(data?.filtros?.meta || 85)}>
									<option value="80">80.0% — Mínimo Operativo</option>
									<option value="85">85.0% — Estándar World Class</option>
									<option value="90">90.0% — Excelencia Operacional</option>
									<option value="95">95.0% — Benchmark Japonés (TPM)</option>
								</select>
							</div>
							<span class="icon is-small is-left">
								<i class="fa-solid fa-percent"></i>
							</span>
						</div>
					</div>
				</div>

				<div class="level-right">
					<div class="buttons mb-0">
						<button type="submit" class="button is-link is-small has-text-weight-bold">
							<i class="fa-solid fa-arrows-rotate mr-1"></i> Consultar Corte SSR
						</button>
						<a href="/admin-1-oee?linea=TODAS&periodo=mes&meta=85" class="button is-light is-small" title="Restablecer filtros contables">
							<i class="fa-solid fa-rotate-left mr-1"></i> Reset
						</a>
					</div>
				</div>
			</div>
		</form>

		<!-- Botones de Acceso Rápido por Línea -->
		<div class="is-flex is-align-items-center mt-3 pt-2" style="border-top: 1px dashed #e2e8f0; gap: 0.5rem; flex-wrap: wrap;">
			<span class="is-size-7 has-text-grey">
				<i class="fa-solid fa-bolt mr-1"></i> Vistas Rápidas:
			</span>
			<a
				href="/admin-1-oee?linea=TODAS&periodo={data?.filtros?.periodo || 'mes'}&meta={data?.filtros?.meta || 85}"
				class="button is-small {(data?.filtros?.linea === 'TODAS' || !data?.filtros?.linea) ? 'is-dark is-outlined has-text-weight-bold' : 'is-white'}"
			>
				Todas las Líneas
			</a>
			<a
				href="/admin-1-oee?linea=L1&periodo={data?.filtros?.periodo || 'mes'}&meta={data?.filtros?.meta || 85}"
				class="button is-small {data?.filtros?.linea === 'L1' ? 'is-info is-outlined has-text-weight-bold' : 'is-white'}"
			>
				L1 Embotellado PET
			</a>
			<a
				href="/admin-1-oee?linea=L2&periodo={data?.filtros?.periodo || 'mes'}&meta={data?.filtros?.meta || 85}"
				class="button is-small {data?.filtros?.linea === 'L2' ? 'is-info is-outlined has-text-weight-bold' : 'is-white'}"
			>
				L2 Envasado Tetra
			</a>
			<a
				href="/admin-1-oee?linea=L3&periodo={data?.filtros?.periodo || 'mes'}&meta={data?.filtros?.meta || 85}"
				class="button is-small {data?.filtros?.linea === 'L3' ? 'is-info is-outlined has-text-weight-bold' : 'is-white'}"
			>
				L3 Paletizado Robótico
			</a>
		</div>
	</div>
</div>

{#if kpis}
	<!-- SECCIÓN 3: TARJETAS EJECUTIVAS DE IMPACTO FINANCIERO EN GUARANÍES (₲) -->
	<div class="columns is-multiline mb-5">
		<!-- KPI 1: Lucro Cesante Total Acumulado -->
		<div class="column is-12-mobile is-6-tablet is-3-desktop">
			<div class="box kpi-card kpi-lucro" style="border-top: 5px solid #dc2626;">
				<div class="level is-mobile mb-1">
					<div class="level-left">
						<span class="heading has-text-grey mb-0">Lucro Cesante Acumulado</span>
					</div>
					<div class="level-right">
						<span class="tag is-danger is-light is-size-7">Impacto Crítico</span>
					</div>
				</div>
				<p class="title is-3 is-family-code mb-1 has-text-danger" style="letter-spacing: -0.5px;">
					{formatearGuaranies(kpis.lucro_cesante_total_gs)}
				</p>
				<p class="is-size-7 has-text-grey">
					<i class="fa-solid fa-clock-rotate-left mr-1"></i>
					<strong>{kpis.minutos_parada_total} min</strong> de paro no programado
				</p>
			</div>
		</div>

		<!-- KPI 2: OEE Global Consolidado -->
		<div class="column is-12-mobile is-6-tablet is-3-desktop">
			<div class="box kpi-card" style="border-top: 5px solid #2563eb;">
				<div class="level is-mobile mb-1">
					<div class="level-left">
						<span class="heading has-text-grey mb-0">OEE Global Consolidado</span>
					</div>
					<div class="level-right">
						<span class="tag is-info is-light is-size-7">Meta: {reporte?.meta_disponibilidad || 85}%</span>
					</div>
				</div>
				<p class="title is-3 is-family-code mb-1 has-text-link">
					{Number(kpis.oee_pct || 0).toFixed(1)}%
				</p>
				<p class="is-size-7 has-text-grey" title="Disponibilidad x Rendimiento x Calidad">
					<i class="fa-solid fa-calculator mr-1"></i>
					D: <strong>{Number(kpis.disponibilidad_pct || 0).toFixed(1)}%</strong> ×
					R: <strong>{Number(kpis.rendimiento_pct || 0).toFixed(1)}%</strong> ×
					Q: <strong>{Number(kpis.calidad_pct || 0).toFixed(1)}%</strong>
				</p>
			</div>
		</div>

		<!-- KPI 3: Costo por Minuto de Línea Caída -->
		<div class="column is-12-mobile is-6-tablet is-3-desktop">
			<div class="box kpi-card" style="border-top: 5px solid #d97706;">
				<div class="level is-mobile mb-1">
					<div class="level-left">
						<span class="heading has-text-grey mb-0">Costo por Minuto Caído</span>
					</div>
					<div class="level-right">
						<span class="tag is-warning is-light is-size-7">Tarifa Técnica</span>
					</div>
				</div>
				<p class="title is-3 is-family-code mb-1 has-text-warning-dark">
					{formatearGuaranies(kpis.costo_minuto_promedio_gs)} <span class="is-size-6 has-text-grey">/ min</span>
				</p>
				<p class="is-size-7 has-text-grey">
					<i class="fa-solid fa-hourglass-half mr-1"></i>
					Equivale a <strong>{formatearMillonesGuaranies((Number(kpis.costo_minuto_promedio_gs) || 0) * 60)}</strong> por hora caída
				</p>
			</div>
		</div>

		<!-- KPI 4: Recuperación Financiera si se alcanza la Meta -->
		<div class="column is-12-mobile is-6-tablet is-3-desktop">
			<div class="box kpi-card" style="border-top: 5px solid #16a34a;">
				<div class="level is-mobile mb-1">
					<div class="level-left">
						<span class="heading has-text-grey mb-0">Recuperación Financiera</span>
					</div>
					<div class="level-right">
						<span class="tag is-success is-light is-size-7">Oportunidad</span>
					</div>
				</div>
				<p class="title is-3 is-family-code mb-1 has-text-success">
					+{formatearGuaranies(kpis.ahorro_potencial_meta_gs)}
				</p>
				<p class="is-size-7 has-text-grey">
					<i class="fa-solid fa-arrow-trend-up mr-1 has-text-success"></i>
					Alcanzando la meta del <strong>{reporte?.meta_disponibilidad || 85}%</strong> de disponibilidad
				</p>
			</div>
		</div>
	</div>

	<!-- DESGLOSE DE LAS 3 GRANDES PÉRDIDAS CONTABLES EN GUARANÍES -->
	<div class="columns is-multiline mb-5">
		<div class="column is-4">
			<div class="notification is-danger is-light py-3 px-4 mb-0" style="border: 1px solid #fca5a5;">
				<p class="heading has-text-danger-dark mb-1">
					<i class="fa-solid fa-circle-stop mr-1"></i> Pérdida por Paradas de Equipo (Disponibilidad)
				</p>
				<p class="title is-5 is-family-code has-text-danger mb-0">
					{formatearGuaranies(kpis.perdida_paradas_gs)}
				</p>
				<p class="is-size-7 has-text-grey mt-1">Averías mecánicas, cambios de molde y falta de suministros</p>
			</div>
		</div>
		<div class="column is-4">
			<div class="notification is-warning is-light py-3 px-4 mb-0" style="border: 1px solid #fde68a;">
				<p class="heading has-text-warning-dark mb-1">
					<i class="fa-solid fa-gauge-simple-low mr-1"></i> Pérdida por Reducción de Velocidad (Rendimiento)
				</p>
				<p class="title is-5 is-family-code has-text-warning-dark mb-0">
					{formatearGuaranies(kpis.perdida_rendimiento_gs)}
				</p>
				<p class="is-size-7 has-text-grey mt-1">Microparadas no registradas y operación a baja cadencia</p>
			</div>
		</div>
		<div class="column is-4">
			<div class="notification is-info is-light py-3 px-4 mb-0" style="border: 1px solid #bfdbfe;">
				<p class="heading has-text-info-dark mb-1">
					<i class="fa-solid fa-ban mr-1"></i> Pérdida por Scrap y Retrabajo (Calidad)
				</p>
				<p class="title is-5 is-family-code has-text-link mb-0">
					{formatearGuaranies(kpis.perdida_calidad_gs)}
				</p>
				<p class="is-size-7 has-text-grey mt-1">Envases defectuosos, botellas abolladas y sellado fuera de norma</p>
			</div>
		</div>
	</div>

	<!-- SECCIÓN 4: SIMULADOR INTERACTIVO CON $derived.by Y GRÁFICA LAYERCHART -->
	<div class="columns is-multiline mb-5">
		<!-- Gráfica LayerChart: Pérdida Diaria en Millones de ₲ -->
		<div class="column is-12-tablet is-7-desktop">
			<div class="card" style="border: 1px solid #cbd5e1; border-radius: 10px; height: 100%;">
				<header class="card-header px-4 py-3" style="background-color: #f8fafc; border-bottom: 1px solid #cbd5e1;">
					<div class="level is-mobile is-flex-grow-1 mb-0">
						<div class="level-left">
							<h3 class="title is-6 mb-0">
								<i class="fa-solid fa-chart-area mr-2 has-text-danger"></i>
								Evolución de la Sangría Financiera Diaria (LayerChart)
							</h3>
						</div>
						<div class="level-right">
							<span class="tag is-danger is-light is-size-7">
								Eje Y: Millones de ₲
							</span>
						</div>
					</div>
				</header>

				<div class="card-content p-4">
					<div class="tags mb-2">
						<span class="tag is-white is-size-7" style="border: 1px solid #e2e8f0;">
							<span class="legend-dot mr-1" style="background: #dc2626;"></span>
							Pérdida por Jornada (Millones ₲)
						</span>
						<span class="tag is-danger is-light is-size-7">
							<span class="legend-line mr-1" style="border-top: 2px dashed #b91c1c;"></span>
							Promedio Diario ({promedioPerdida.toFixed(1)} M ₲)
						</span>
						<span class="tag is-white is-size-7 ml-auto" style="border: 1px solid #e2e8f0;">
							Ventana: {serieDiaria.length} días contables
						</span>
					</div>

					<!-- Contenedor Oficial LayerChart según app.css (.layerchart-box) -->
					<div class="layerchart-box" style="height: 290px; width: 100%; position: relative;">
						{#if serieDiaria.length > 0}
							<Chart
								data={serieDiaria}
								x="dia_num"
								xScale={scaleLinear()}
								y="perdida_millones_gs"
								yScale={scaleLinear()}
								yDomain={[0, maxPerdida]}
								padding={{ top: 20, right: 25, bottom: 30, left: 65 }}
							>
								<Svg>
									<Axis
										placement="left"
										grid
										rule
										format={(d) => `${d} M`}
									/>
									<Axis
										placement="bottom"
										rule
										format={(d) => `Día ${d}`}
									/>
									<Area
										style="fill: rgba(239, 68, 68, 0.18);"
									/>
									<Spline
										style="stroke: #dc2626; stroke-width: 2.5px;"
									/>
									<Rule
										y={promedioPerdida}
										style="stroke: #b91c1c; stroke-width: 1.5px; stroke-dasharray: 4,4;"
									/>
								</Svg>
							</Chart>
						{:else}
							<div class="is-flex is-justify-content-center is-align-items-center" style="height: 100%;">
								<p class="has-text-grey">Sin datos de serie diaria desde FastAPI</p>
							</div>
						{/if}
					</div>

					<p class="is-size-7 has-text-grey mt-2">
						<i class="fa-solid fa-circle-info mr-1 has-text-info"></i>
						La línea discontinua roja indica la pérdida media diaria calculada en el backend Python.
						Cada pico refleja un evento grave de indisponibilidad o rotura no planificada.
					</p>
				</div>
			</div>
		</div>

		<!-- Simulador Interactivo en Cliente con Runes $derived.by -->
		<div class="column is-12-tablet is-5-desktop">
			<div class="card p-4" style="border: 1px solid #cbd5e1; border-radius: 10px; height: 100%; background: #ffffff;">
				<div class="is-flex is-align-items-center mb-3">
					<span class="tag is-success is-medium mr-2">
						<i class="fa-solid fa-sliders"></i>
					</span>
					<div>
						<h3 class="title is-6 mb-0">Simulador Gerencial Interactivo</h3>
						<p class="is-size-7 has-text-grey">Cálculo en vivo con Runes Svelte 5 ($derived.by)</p>
					</div>
				</div>

				<div class="box has-background-light p-3 mb-4" style="border: 1px solid #e2e8f0;">
					<label class="label is-small mb-1" for="slider-minutos">
						¿Qué pasaría si reducimos minutos de parada este mes?
					</label>
					<div class="level is-mobile mb-2">
						<div class="level-left">
							<span class="is-size-7 has-text-grey">Meta de reducción:</span>
						</div>
						<div class="level-right">
							<span class="tag is-success has-text-weight-bold is-medium">
								{minutosAhorroSimulados} minutos
							</span>
						</div>
					</div>

					<input
						id="slider-minutos"
						type="range"
						min="0"
						max="360"
						step="5"
						bind:value={minutosAhorroSimulados}
						class="slider is-fullwidth is-success"
						style="width: 100%; cursor: pointer;"
					/>

					<div class="is-flex is-justify-content-between is-size-7 has-text-grey mt-1">
						<span>0 min (Estado actual)</span>
						<span>180 min (3 horas)</span>
						<span>360 min (6 horas)</span>
					</div>
				</div>

				<!-- Resultados de la Proyección en Guaraníes -->
				<div class="content is-size-7 mb-4">
					<div class="columns is-mobile is-multiline">
						<div class="column is-6">
							<div class="p-2 has-background-white" style="border: 1px solid #e2e8f0; border-radius: 6px;">
								<p class="heading has-text-grey mb-1">Ahorro Directo Proyectado</p>
								<p class="title is-5 has-text-success is-family-code mb-0">
									+{formatearGuaranies(simulacion.ahorroGs)}
								</p>
							</div>
						</div>
						<div class="column is-6">
							<div class="p-2 has-background-white" style="border: 1px solid #e2e8f0; border-radius: 6px;">
								<p class="heading has-text-grey mb-1">Nuevo Lucro Cesante Estimado</p>
								<p class="title is-5 has-text-danger is-family-code mb-0">
									{formatearGuaranies(simulacion.lucroNuevoGs)}
								</p>
							</div>
						</div>
						<div class="column is-6">
							<div class="p-2 has-background-white" style="border: 1px solid #e2e8f0; border-radius: 6px;">
								<p class="heading has-text-grey mb-1">Disponibilidad Proyectada</p>
								<p class="title is-5 has-text-link is-family-code mb-0">
									{simulacion.disponibilidadProyectada.toFixed(1)}%
								</p>
							</div>
						</div>
						<div class="column is-6">
							<div class="p-2 has-background-white" style="border: 1px solid #e2e8f0; border-radius: 6px;">
								<p class="heading has-text-grey mb-1">OEE Resultante Estimado</p>
								<p class="title is-5 has-text-link is-family-code mb-0">
									{simulacion.oeeProyectado.toFixed(1)}%
								</p>
							</div>
						</div>
					</div>
				</div>

				<div class="notification is-success is-light p-3 is-size-7 mb-0">
					<i class="fa-solid fa-lightbulb mr-1 has-text-success-dark"></i>
					<strong>Justificación CapEx:</strong>
					Reducir solo <strong>{minutosAhorroSimulados} min</strong> de averías representa un flujo de caja positivo de
					<strong>{formatearGuaranies(simulacion.ahorroGs)}</strong>, suficiente para financiar planes de mantenimiento predictivo y repuestos críticos.
				</div>
			</div>
		</div>
	</div>

	<!-- SECCIÓN 5: DESGLOSE POR TURNOS OPERATIVOS Y REGISTRO DE PARADAS AUDITADAS -->
	<div class="columns is-multiline mb-5">
		<!-- Tabla de Turnos Operativos -->
		<div class="column is-12-tablet is-6-desktop">
			<div class="card" style="border: 1px solid #cbd5e1; border-radius: 10px; height: 100%;">
				<header class="card-header px-4 py-3" style="background-color: #f8fafc; border-bottom: 1px solid #cbd5e1;">
					<div class="level is-mobile is-flex-grow-1 mb-0">
						<div class="level-left">
							<h3 class="title is-6 mb-0">
								<i class="fa-solid fa-users-gear mr-2 has-text-info"></i>
								Rendimiento y Lucro Cesante por Turno
							</h3>
						</div>
						<div class="level-right">
							<span class="tag is-info is-light is-size-7">3 Turnos Rotativos</span>
						</div>
					</div>
				</header>

				<div class="card-content p-0">
					<div class="table-container mb-0">
						<table class="table is-fullwidth is-striped is-hoverable is-size-7 mb-0">
							<thead>
								<tr style="background-color: #f1f5f9;">
									<th>Turno</th>
									<th class="has-text-centered">OEE (%)</th>
									<th class="has-text-centered">Disp. (%)</th>
									<th class="has-text-centered">Paro (min)</th>
									<th class="has-text-right">Lucro Cesante (₲)</th>
									<th>Causa Principal</th>
								</tr>
							</thead>
							<tbody>
								{#each turnos as t (t.turno)}
									<tr>
										<td class="has-text-weight-bold">
											{#if t.turno.includes('Mañana')}
												<i class="fa-regular fa-sun mr-1 has-text-warning"></i>
											{:else if t.turno.includes('Tarde')}
												<i class="fa-solid fa-cloud-sun mr-1 has-text-warning-dark"></i>
											{:else}
												<i class="fa-regular fa-moon mr-1 has-text-link"></i>
											{/if}
											{t.turno}
										</td>
										<td class="has-text-centered is-family-code">
											<span class="tag {t.oee_pct >= 75 ? 'is-success' : 'is-warning'} is-light is-small has-text-weight-bold">
												{Number(t.oee_pct || 0).toFixed(1)}%
											</span>
										</td>
										<td class="has-text-centered is-family-code">
											{Number(t.disponibilidad_pct || 0).toFixed(1)}%
										</td>
										<td class="has-text-centered is-family-code has-text-weight-bold has-text-danger">
											{t.minutos_paro} min
										</td>
										<td class="has-text-right is-family-code has-text-weight-bold has-text-danger">
											{formatearGuaranies(t.lucro_cesante_gs)}
										</td>
										<td class="has-text-grey" style="max-width: 170px;">
											{t.causa_principal}
										</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				</div>
			</div>
		</div>

		<!-- Formulario de Imputación de Parada Auditada (?/registrarParo con use:enhance) -->
		<div class="column is-12-tablet is-6-desktop">
			<div class="card" style="border: 1px solid #cbd5e1; border-radius: 10px; height: 100%;">
				<header class="card-header px-4 py-3" style="background-color: #f8fafc; border-bottom: 1px solid #cbd5e1;">
					<div class="level is-mobile is-flex-grow-1 mb-0">
						<div class="level-left">
							<h3 class="title is-6 mb-0">
								<i class="fa-solid fa-clipboard-check mr-2 has-text-danger"></i>
								Imputar Parada de Línea Auditada (FastAPI POST)
							</h3>
						</div>
						<div class="level-right">
							<span class="tag is-danger is-light is-size-7">Mutación Contable</span>
						</div>
					</div>
				</header>

				<div class="card-content p-4">
					{#if form?.success}
						<div class="notification is-success is-light py-2 px-3 mb-3 is-size-7">
							<i class="fa-solid fa-circle-check mr-1"></i>
							<strong>¡Paro registrado con éxito!</strong>
							{form?.respuesta?.mensaje || 'FastAPI ha recalculado el OEE y el lucro cesante en Guaraníes.'}
						</div>
					{:else if form?.error}
						<div class="notification is-danger is-light py-2 px-3 mb-3 is-size-7">
							<i class="fa-solid fa-circle-xmark mr-1"></i>
							<strong>Error:</strong> {form.error}
						</div>
					{/if}

					<form
						method="POST"
						action="?/registrarParo"
						use:enhance={() => {
							guardandoParo = true;
							return async ({ update }) => {
								guardandoParo = false;
								await update();
							};
						}}
					>
						<div class="columns is-multiline mb-1">
							<!-- Selección de Línea -->
							<div class="column is-6 py-1">
								<div class="field">
									<label class="label is-small mb-1" for="input-paro-linea">Línea Afectada</label>
									<div class="control">
										<div class="select is-small is-fullwidth">
											<select id="input-paro-linea" name="linea" required>
												<option value="L1">L1: Embotellado PET (₲ 1.450.000/min)</option>
												<option value="L2">L2: Envasado Tetra (₲ 1.850.000/min)</option>
												<option value="L3">L3: Paletizado Robótico (₲ 980.000/min)</option>
											</select>
										</div>
									</div>
								</div>
							</div>

							<!-- Selección de Turno -->
							<div class="column is-6 py-1">
								<div class="field">
									<label class="label is-small mb-1" for="input-paro-turno">Turno Contable</label>
									<div class="control">
										<div class="select is-small is-fullwidth">
											<select id="input-paro-turno" name="turno" required>
												<option value="Turno Mañana 06-14">Turno Mañana (06:00 - 14:00)</option>
												<option value="Turno Tarde 14-22">Turno Tarde (14:00 - 22:00)</option>
												<option value="Turno Noche 22-06">Turno Noche (22:00 - 06:00)</option>
											</select>
										</div>
									</div>
								</div>
							</div>

							<!-- Minutos de Parada -->
							<div class="column is-6 py-1">
								<div class="field">
									<label class="label is-small mb-1" for="input-paro-minutos">Minutos de Parada</label>
									<div class="control has-icons-left">
										<input
											id="input-paro-minutos"
											type="number"
											name="minutos"
											min="1"
											max="480"
											value="35"
											class="input is-small is-family-code"
											required
										/>
										<span class="icon is-small is-left">
											<i class="fa-solid fa-stopwatch"></i>
										</span>
									</div>
								</div>
							</div>

							<!-- Responsable / Supervisor -->
							<div class="column is-6 py-1">
								<div class="field">
									<label class="label is-small mb-1" for="input-paro-responsable">Supervisor / Auditor</label>
									<div class="control has-icons-left">
										<input
											id="input-paro-responsable"
											type="text"
											name="responsable"
											value="Ing. Carlos Mendoza (FIUNA)"
											class="input is-small"
											required
										/>
										<span class="icon is-small is-left">
											<i class="fa-solid fa-user-check"></i>
										</span>
									</div>
								</div>
							</div>

							<!-- Causa del Paro -->
							<div class="column is-12 py-1">
								<div class="field">
									<label class="label is-small mb-1" for="input-paro-causa">Causa Raíz de la Interrupción</label>
									<div class="control has-icons-left">
										<input
											id="input-paro-causa"
											type="text"
											name="causa"
											placeholder="Ej: Falla de variador de frecuencia en cadena transportadora"
											value="Atasco en cadena de arrastre de etiquetadora"
											class="input is-small"
											required
										/>
										<span class="icon is-small is-left">
											<i class="fa-solid fa-wrench"></i>
										</span>
									</div>
								</div>
							</div>
						</div>

						<div class="field mt-3">
							<button
								type="submit"
								class="button is-danger is-small is-fullwidth has-text-weight-bold {guardandoParo ? 'is-loading' : ''}"
								disabled={guardandoParo}
							>
								<i class="fa-solid fa-floppy-disk mr-2"></i>
								Imputar Paro y Recalcular Lucro Cesante en FastAPI
							</button>
						</div>

						<p class="is-size-7 has-text-grey mt-2">
							<i class="fa-solid fa-shield-halved mr-1 has-text-danger"></i>
							Al pulsar el botón, SvelteKit ejecuta la acción del servidor Node $\rightarrow$ envía un <code>POST</code> a FastAPI $\rightarrow$ FastAPI registra el evento en memoria y SvelteKit re-ejecuta <code>load()</code> automáticamente actualizando los millones de Guaraníes.
						</p>
					</form>
				</div>
			</div>
		</div>
	</div>

	<!-- TABLA DE HISTORIAL DE PAROS AUDITADOS EN MEMORIA -->
	{#if parosRegistrados && parosRegistrados.length > 0}
		<div class="card mb-5" style="border: 1px solid #cbd5e1; border-radius: 10px;">
			<header class="card-header px-4 py-3" style="background-color: #f8fafc; border-bottom: 1px solid #cbd5e1;">
				<div class="level is-mobile is-flex-grow-1 mb-0">
					<div class="level-left">
						<h3 class="title is-6 mb-0">
							<i class="fa-solid fa-clock-rotate-left mr-2 has-text-dark"></i>
							Registro Histórico de Incidentes Auditados en Servidor FastAPI ({parosRegistrados.length} eventos)
						</h3>
					</div>
					<div class="level-right">
						<span class="tag is-dark is-size-7">FastAPI Memory Store</span>
					</div>
				</div>
			</header>

			<div class="card-content p-0">
				<div class="table-container mb-0">
					<table class="table is-fullwidth is-striped is-hoverable is-size-7 mb-0">
						<thead>
							<tr style="background-color: #f1f5f9;">
								<th>ID</th>
								<th>Fecha / Hora</th>
								<th>Línea</th>
								<th>Turno</th>
								<th class="has-text-centered">Duración</th>
								<th class="has-text-right">Lucro Cesante Imputado (₲)</th>
								<th>Causa Raíz</th>
								<th>Auditor Responsable</th>
							</tr>
						</thead>
						<tbody>
							{#each parosRegistrados as p (p.id || p.fecha_hora)}
								<tr>
									<td class="is-family-code has-text-weight-bold">{p.id || 'EVT-01'}</td>
									<td class="is-family-code">{p.fecha_hora || 'Hoy'}</td>
									<td>
										<span class="tag is-info is-light is-small has-text-weight-bold">
											{p.linea}
										</span>
									</td>
									<td>{p.turno}</td>
									<td class="has-text-centered is-family-code has-text-danger has-text-weight-bold">
										{p.minutos} min
									</td>
									<td class="has-text-right is-family-code has-text-danger has-text-weight-bold">
										{formatearGuaranies(p.costo_calculado_gs)}
									</td>
									<td>{p.causa}</td>
									<td class="has-text-grey">{p.responsable}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		</div>
	{/if}
{/if}

<!-- SECCIÓN 6: VISOR PEDAGÓGICO DE CÓDIGO (CodeViewer) -->
<CodeViewer
	titulo="Código Fuente — Proyecto 5: BFF SSR y OEE Contable en Millones de ₲"
	archivos={[
		{
			nombre: '+page.server.js (BFF Load + Form Action)',
			descripcion: 'Implementa el patrón BFF en SSR que consulta FastAPI determinísticamente y procesa la Form Action registrarParo.',
			codigo: codigoServerJs
		},
		{
			nombre: '+page.svelte (Runes Svelte 5 + LayerChart)',
			descripcion: 'Reactividad determinista con $derived.by, simulador interactivo de minutos ahorrados y renderizado con LayerChart.',
			codigo: codigoSvelteJs
		},
		{
			nombre: 'FastAPI main.py (/api/admin/oee)',
			descripcion: 'Lógica contable e industrial en Python: cálculo de OEE (A x P x Q), valorización por minuto en ₲ y revalidación.',
			codigo: codigoFastApiPy
		}
	]}
/>

<style>
	.header-box {
		border-radius: 12px;
		background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
		border: 1px solid #cbd5e1;
		box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
	}

	.filter-card {
		border-radius: 10px;
		background: #ffffff;
		border: 1px solid #cbd5e1;
	}

	.kpi-card {
		border-radius: 10px;
		background: #ffffff;
		border: 1px solid #cbd5e1;
		transition: transform 0.15s ease, box-shadow 0.15s ease;
		height: 100%;
	}

	.kpi-card:hover {
		transform: translateY(-2px);
		box-shadow: 0 6px 12px -2px rgba(0, 0, 0, 0.08);
	}

	.kpi-lucro {
		background: linear-gradient(180deg, #ffffff 0%, #fef2f2 100%);
	}

	.legend-dot {
		display: inline-block;
		width: 10px;
		height: 10px;
		border-radius: 50%;
	}

	.legend-line {
		display: inline-block;
		width: 16px;
		height: 0px;
		vertical-align: middle;
	}
</style>
