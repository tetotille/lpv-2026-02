<script>
	/**
	 * Proyecto 8 (Admin 4): "Conciliación Contable de Lotes (MES vs. ERP), Mermas de Materia Prima y Auditoría Financiera"
	 * Ruta: /admin-4-conciliacion-lotes
	 *
	 * Svelte 5 Runes: $props, $state, $derived, $derived.by, $effect
	 * Cátedra: Lenguajes de Programación Visual — FIUNA
	 *
	 * Arquitectura de Tiempo Real Administrativo:
	 * - 100% alimentado por FastAPI (http://localhost:8007/api/admin/conciliacion-lotes)
	 * - Cierre de balance de masa por lote (Batch) cruzando telemetría de campo con ERP
	 * - Pista de auditoría forense y dictamen con use:enhance y revalidación automática
	 */

	import { enhance } from '$app/forms';
	import { FASTAPI_BASE_URL } from '$lib/config.js';
	import { formatearGuaranies, formatearMillonesGuaranies } from '$lib/utils/moneda.js';
	import { Chart, Svg, Spline, Area, Axis, Rule } from 'layerchart';
	import { scaleLinear } from 'd3-scale';
	import CodeViewer from '$lib/components/CodeViewer.svelte';

	let { data, form } = $props();

	// Extracción reactiva de datos devueltos por el servidor SvelteKit (+page.server.js)
	const conciliacion = $derived(data?.conciliacion || null);
	const resumen = $derived(conciliacion?.resumen_financiero || null);
	const lotes = $derived(conciliacion?.lotes || []);
	const serieChart = $derived(conciliacion?.serie_lotes_chart || []);
	const estadoFiltroActivo = $derived(data?.estadoFiltro || 'TODOS');

	// Estado local interactivo para el panel de dictamen de auditoría
	let loteSeleccionadoId = $state('LOT-2026-802');
	let accionDictamen = $state('BLOQUEADO_RECALIBRACION');
	let auditorNombre = $state('Lic. Martín Cáceres — Auditoría Contable FIUNA');
	let causaRaiz = $state('Deriva metrológica en caudalímetro Coriolis FIT-201 (+4.2%)');
	let observacion = $state(
		'Se ordena retención contable del lote en ERP y envío inmediato de orden de calibración metrológica en campo.'
	);
	let enviandoDictamen = $state(false);

	// Lote enfocado reactivamente a partir del ID seleccionado
	const loteSeleccionado = $derived.by(() => {
		if (!lotes || lotes.length === 0) return null;
		const encontrado = lotes.find((l) => l.lote_id === loteSeleccionadoId);
		return encontrado || lotes[0];
	});

	// Sincronización inicial con el primer lote anómalo o pendiente
	$effect(() => {
		if (lotes.length > 0 && !lotes.some((l) => l.lote_id === loteSeleccionadoId)) {
			const anomalo = lotes.find((l) => l.merma_real_pct > (l.merma_tolerada_pct || 1.5));
			if (anomalo) {
				loteSeleccionadoId = anomalo.lote_id;
			} else {
				loteSeleccionadoId = lotes[0].lote_id;
			}
		}
	});

	// Selección rápida de lote desde la tabla
	function seleccionarLote(lote) {
		loteSeleccionadoId = lote.lote_id;
		if (lote.merma_real_pct > (lote.merma_tolerada_pct || 1.5)) {
			accionDictamen = 'BLOQUEADO_RECALIBRACION';
			causaRaiz =
				lote.sensor_sospechoso && !lote.sensor_sospechoso.startsWith('Ninguno')
					? `Desvío metrológico detectado en ${lote.sensor_sospechoso}`
					: 'Merma física crítica superior a tolerancia contable (> 1.5%)';
			observacion = `Se constató merma de ${lote.merma_real_pct.toFixed(2)}% generando un desvío no justificado de ${formatearGuaranies(lote.desvio_sobre_tolerancia_gs)}. Bloquear despacho comercial.`;
		} else {
			accionDictamen = 'APROBADO_CONFORME';
			causaRaiz = 'Merma de proceso dentro del límite de control estocástico (<= 1.5%)';
			observacion = `Balance de masa consistente (${lote.merma_real_pct.toFixed(2)}%). Remisión ERP coincide con caudalímetro MES.`;
		}
	}

	// Dominio máximo dinámico para LayerChart
	const maxMerma = $derived.by(() => {
		if (!serieChart || serieChart.length === 0) return 5.0;
		const max = Math.max(...serieChart.map((d) => Number(d.merma_real_pct) || 0));
		return Math.max(max * 1.18, 4.5);
	});

	// Fragmentos pedagógicos de código fuente
	const codigoServerJs = `// +page.server.js — Proyecto 8: Conciliación Contable de Lotes (BFF + Form Actions)
import { FASTAPI_BASE_URL } from '$lib/config.js';
import { fail } from '@sveltejs/kit';

export async function load({ url, fetch }) {
    const estado_filtro = url.searchParams.get('estado') || 'TODOS';
    const apiFiltro = estado_filtro === 'ANOMALIA' ? 'TODOS' : estado_filtro;
    const endpoint = \`\${FASTAPI_BASE_URL}/api/admin/conciliacion-lotes?estado_filtro=\${encodeURIComponent(apiFiltro)}\`;

    try {
        const res = await fetch(endpoint);
        if (!res.ok) {
            return {
                fastapiOnline: false,
                errorConexion: \`No se pudo conectar con FastAPI (\${FASTAPI_BASE_URL}/api/admin/conciliacion-lotes)\`
            };
        }
        const conciliacion = await res.json();
        if (estado_filtro === 'ANOMALIA' && Array.isArray(conciliacion.lotes)) {
            conciliacion.lotes = conciliacion.lotes.filter(
                (l) => l.merma_real_pct > (l.merma_tolerada_pct || 1.5)
            );
        }
        return {
            fastapiOnline: true,
            estadoFiltro: estado_filtro,
            endpointConsultado: \`\${FASTAPI_BASE_URL}/api/admin/conciliacion-lotes?estado_filtro=\${estado_filtro}\`,
            conciliacion
        };
    } catch (err) {
        return {
            fastapiOnline: false,
            errorConexion: \`No se pudo conectar con FastAPI (\${FASTAPI_BASE_URL}/api/admin/conciliacion-lotes)\`
        };
    }
}

export const actions = {
    emitirDictamen: async ({ request, fetch }) => {
        const formData = await request.formData();
        const lote_id = formData.get('lote_id')?.toString() || '';
        const accion = formData.get('accion')?.toString() || 'APROBADO_CONFORME';
        const auditor = formData.get('auditor')?.toString() || 'Auditor Contable-Metrológico';
        const causa_raiz = formData.get('causa_raiz')?.toString() || 'Sin causa especificada';
        const observacion = formData.get('observacion')?.toString() || '';

        const res = await fetch(\`\${FASTAPI_BASE_URL}/api/admin/conciliacion-lotes/dictamen\`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ lote_id, accion, auditor, causa_raiz, observacion })
        });

        const body = await res.json().catch(() => ({}));
        if (!res.ok) {
            return fail(res.status, { error: body.detail || 'Error al registrar dictamen en FastAPI' });
        }
        return { success: true, respuesta: body };
    }
};`;

	const codigoSvelteJs = `// +page.svelte — Svelte 5 Runes + LayerChart + Auditoría Contable-Metrológica
let { data, form } = $props();

const conciliacion = $derived(data?.conciliacion || null);
const resumen = $derived(conciliacion?.resumen_financiero || null);
const serieChart = $derived(conciliacion?.serie_lotes_chart || []);

// Gráfica de Mermas por Lote vs. Tolerancia Contable Máxima (1.5%)
<div class="layerchart-box">
    <Chart
        data={serieChart}
        x="idx"
        y="merma_real_pct"
        xScale={scaleLinear()}
        yScale={scaleLinear()}
        yDomain={[0, maxMerma]}
        padding={{ top: 20, right: 20, bottom: 35, left: 55 }}
    >
        <Svg>
            <Axis placement="left" grid rule format={(d) => \`\${d.toFixed(1)}%\`} />
            <Axis placement="bottom" rule format={(d) => \`L\${d}\`} />
            <Area style="fill: rgba(220, 38, 38, 0.15);" />
            <Spline style="stroke: #dc2626; stroke-width: 2.5px;" />
            <Rule y={1.5} style="stroke: #d97706; stroke-width: 2px; stroke-dasharray: 4,4;" />
        </Svg>
    </Chart>
</div>

// Emisión de Dictamen Contable y Metrológico con use:enhance
<form method="POST" action="?/emitirDictamen" use:enhance={() => {
    enviandoDictamen = true;
    return async ({ update }) => {
        await update();
        enviandoDictamen = false;
    };
}}>
    <input type="hidden" name="lote_id" value={loteSeleccionadoId} />
    ...
</form>`;

	const codigoFastApiPy = `# backend_fastapi/main.py — Endpoints de Conciliación de Lotes y Dictámenes
@app.get("/api/admin/conciliacion-lotes", summary="Conciliación de masa MES vs. ERP y auditoría de desvíos")
async def get_conciliacion_lotes(estado_filtro: str = Query("TODOS")):
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
    lote = next((l for l in lotes_conciliacion_db if l["lote_id"] == payload.lote_id), None)
    if not lote:
        raise HTTPException(status_code=404, detail="Lote no encontrado")

    lote["estado_auditoria"] = payload.accion
    lote["dictamen_auditor"] = f"{payload.observacion} (Causa raíz: {payload.causa_raiz})"
    lote["auditor_firmante"] = payload.auditor

    registrar_evento(
        nivel="WARN" if payload.accion == "BLOQUEADO_RECALIBRACION" else "INFO",
        origen=f"AuditoríaERP/{payload.lote_id}",
        mensaje=f"Dictamen {payload.accion} emitido por {payload.auditor}: {payload.causa_raiz}"
    )

    return {"ok": True, "lote_actualizado": lote, "resumen_financiero": calcular_resumen_conciliacion()}`;
</script>

<svelte:head>
	<title>Proyecto 8: Conciliación Contable de Lotes (MES vs. ERP) — FIUNA</title>
</svelte:head>

<!-- BARRA DE NAVEGACIÓN ADMINISTRATIVA -->
<nav class="breadcrumb has-succeeds-separator mb-4 is-small" aria-label="breadcrumbs">
	<ul>
		<li><a href="/"><i class="fa-solid fa-house mr-1"></i> Inicio</a></li>
		<li><a href="/admin-1-oee">Admin 1: OEE &amp; Lucro Cesante</a></li>
		<li><a href="/admin-2-energia-ande">Admin 2: Auditoría ANDE</a></li>
		<li><a href="/admin-3-capex-mantenimiento">Admin 3: CapEx &amp; Idempotencia</a></li>
		<li class="is-active">
			<a href="/admin-4-conciliacion-lotes" aria-current="page" class="has-text-weight-bold has-text-link">
				Admin 4: Conciliación de Lotes
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
					<span class="tag is-dark">Proyecto 8</span>
					<span class="tag is-primary has-text-weight-bold">Admin 4: Conciliación Contable</span>
					{#if data?.fastapiOnline}
						<span class="tag is-success">
							<i class="fa-solid fa-circle-check mr-1"></i> FastAPI Online (:8007)
						</span>
					{:else}
						<span class="tag is-danger">
							<i class="fa-solid fa-triangle-exclamation mr-1"></i> FastAPI Desconectado
						</span>
					{/if}
				</div>
				<h1 class="title is-3 mb-1">
					<i class="fa-solid fa-scale-balanced has-text-link mr-2"></i>
					Conciliación Contable de Lotes (MES vs. ERP) y Auditoría de Mermas
				</h1>
				<p class="subtitle is-6 has-text-grey">
					Cátedra: Lenguajes de Programación Visual — Facultad de Ingeniería, Universidad Nacional de Asunción (FIUNA)
				</p>
			</div>
		</div>
		<div class="level-right">
			<div class="tags are-medium">
				<span class="tag is-info is-light">
					<i class="fa-solid fa-server mr-1"></i>
					SSR BFF + Form Actions
				</span>
				<span class="tag is-warning is-light">
					<i class="fa-solid fa-coins mr-1"></i>
					Valores en Guaraníes (₲)
				</span>
			</div>
		</div>
	</div>

	<!-- Trazabilidad Técnica del Endpoint FastAPI -->
	<article class="message is-info is-small mb-3">
		<div class="message-body p-2">
			<div class="columns is-vcentered is-mobile is-multiline">
				<div class="column is-12-mobile is-8-tablet">
					<span class="has-text-weight-bold mr-2">
						<i class="fa-solid fa-network-wired mr-1"></i> Endpoint Auditado:
					</span>
					<code class="has-text-link">
						{data?.endpointConsultado || `${FASTAPI_BASE_URL}/api/admin/conciliacion-lotes`}
					</code>
				</div>
				<div class="column is-12-mobile is-4-tablet has-text-right-tablet">
					<span class="tag is-light is-info">
						<i class="fa-solid fa-arrows-rotate mr-1"></i>
						Tiempo Real Administrativo (Batch)
					</span>
				</div>
			</div>
		</div>
	</article>

	<!-- Fundamentación de Integración Física MES vs. Contabilidad ERP -->
	<div class="content is-small has-text-grey-dark mb-0">
		<p class="mb-2">
			<strong>Fundamento Físico-Contable:</strong> Al cierre de cada lote industrial (<em>Batch</em>),
			la masa acumulada por caudalímetros másicos Coriolis y celdas de carga en silos (nivel de piso de planta <strong>MES</strong>)
			debe conciliarse rigurosamente con las remisiones contables de almacén y facturación (nivel <strong>ERP</strong>).
			En industrias de bebidas y alimentos en Paraguay, una deriva no calibrada de tan solo <strong>+3.5%</strong> en una celda de carga
			o una microfuga en válvulas dosificadoras representa mermas de <strong>decenas de millones de Guaraníes</strong> por cada lote de producción.
		</p>
		<p class="mb-0">
			<strong>Contraste Metodológico:</strong> Mientras el <em>Tiempo Real Físico</em> (Proyectos 1 a 4) opera a milisegundos con telemetría continua para control de proceso,
			el <em>Tiempo Real Administrativo</em> (Proyectos 5 a 8) opera por transacciones atómicas al cierre de lote, exigiendo inmutabilidad contable,
			dictamen formal del auditor financiero y emisión de órdenes de bloqueo y recalibración de instrumentos en FastAPI.
		</p>
	</div>
</div>

<!-- ALERTA SI FASTAPI ESTÁ OFFLINE -->
{#if !data?.fastapiOnline}
	<div class="notification is-danger is-light mb-5" style="border-left: 6px solid #dc2626;">
		<div class="is-flex is-align-items-start">
			<span class="icon is-large mr-3 has-text-danger">
				<i class="fa-solid fa-triangle-exclamation fa-2x"></i>
			</span>
			<div>
				<h3 class="title is-5 mb-1 has-text-danger-dark">Error de Conexión con el Servidor Industrial FastAPI</h3>
				<p class="mb-2">
					{data?.errorConexion || 'No se pudo contactar el endpoint /api/admin/conciliacion-lotes en FastAPI (:8007).'}
				</p>
				<p class="is-size-7">
					Verifique que el backend Python esté ejecutándose con:
					<code>cd backend_fastapi &amp;&amp; uvicorn main:app --port 8007 --reload</code>
				</p>
			</div>
		</div>
	</div>
{/if}

<!-- RETROALIMENTACIÓN DE FORM ACTION (DICTAMEN DE AUDITORÍA) -->
{#if form?.success}
	<div class="notification is-success is-light mb-5" style="border-left: 6px solid #16a34a;">
		<button class="delete" aria-label="cerrar" onclick={() => (form = null)}></button>
		<div class="is-flex is-align-items-center">
			<span class="icon is-medium mr-2 has-text-success">
				<i class="fa-solid fa-circle-check fa-lg"></i>
			</span>
			<div>
				<strong>¡Dictamen Registrado con Éxito en FastAPI!</strong>
				<p class="is-size-7 mt-1">
					{form.respuesta?.mensaje || 'El dictamen ha sido asentado en el libro contable de auditoría y en los eventos SCADA.'}
				</p>
			</div>
		</div>
	</div>
{:else if form?.error}
	<div class="notification is-danger is-light mb-5" style="border-left: 6px solid #dc2626;">
		<button class="delete" aria-label="cerrar" onclick={() => (form = null)}></button>
		<div class="is-flex is-align-items-center">
			<span class="icon is-medium mr-2 has-text-danger">
				<i class="fa-solid fa-circle-xmark fa-lg"></i>
			</span>
			<div>
				<strong>Error al Registrar Dictamen:</strong> {form.error}
			</div>
		</div>
	</div>
{/if}

{#if resumen}
	<!-- SECCIÓN 2: CUATRO TARJETAS DE KPIS FINANCIEROS Y METROLÓGICOS -->
	<div class="columns is-multiline mb-5">
		<!-- KPI 1: Valor Total de Producción Auditada -->
		<div class="column is-12-mobile is-6-tablet is-3-desktop">
			<div class="card kpi-card p-4">
				<div class="level is-mobile mb-2">
					<div class="level-left">
						<span class="tag is-info is-light has-text-weight-bold">Producción Fiscal</span>
					</div>
					<div class="level-right">
						<span class="icon has-text-info">
							<i class="fa-solid fa-boxes-stacked"></i>
						</span>
					</div>
				</div>
				<p class="is-size-7 has-text-grey mb-1">Valor Total de Producción Auditada</p>
				<h2 class="title is-4 mb-1 has-text-link-dark">
					{formatearGuaranies(resumen.valor_total_produccion_gs)}
				</h2>
				<p class="is-size-7 has-text-grey">
					<i class="fa-solid fa-arrow-trend-up mr-1 has-text-info"></i>
					{formatearMillonesGuaranies(resumen.valor_total_produccion_gs)} valorizados en ERP
				</p>
			</div>
		</div>

		<!-- KPI 2: Pérdida Total por Mermas Físicas -->
		<div class="column is-12-mobile is-6-tablet is-3-desktop">
			<div class="card kpi-card kpi-warning p-4">
				<div class="level is-mobile mb-2">
					<div class="level-left">
						<span class="tag is-warning is-light has-text-weight-bold">Mermas Totales</span>
					</div>
					<div class="level-right">
						<span class="icon has-text-warning">
							<i class="fa-solid fa-filter-circle-dollar"></i>
						</span>
					</div>
				</div>
				<p class="is-size-7 has-text-grey mb-1">Pérdida Total por Mermas Físicas</p>
				<h2 class="title is-4 mb-1 has-text-warning-dark">
					{formatearGuaranies(resumen.perdida_total_mermas_gs)}
				</h2>
				<p class="is-size-7 has-text-grey">
					<i class="fa-solid fa-droplet-slash mr-1 has-text-warning"></i>
					Masa no recuperada en proceso (₲)
				</p>
			</div>
		</div>

		<!-- KPI 3: Desvío Auditable No Justificado -->
		<div class="column is-12-mobile is-6-tablet is-3-desktop">
			<div class="card kpi-card kpi-danger p-4">
				<div class="level is-mobile mb-2">
					<div class="level-left">
						<span class="tag is-danger is-light has-text-weight-bold">&gt; 1.5% Tolerancia</span>
					</div>
					<div class="level-right">
						<span class="icon has-text-danger">
							<i class="fa-solid fa-triangle-exclamation"></i>
						</span>
					</div>
				</div>
				<p class="is-size-7 has-text-grey mb-1">Desvío Auditable No Justificado</p>
				<h2 class="title is-4 mb-1 has-text-danger">
					{formatearGuaranies(resumen.desvio_auditable_no_justificado_gs)}
				</h2>
				<p class="is-size-7 has-text-danger-dark">
					<i class="fa-solid fa-circle-exclamation mr-1"></i>
					Pérdida por descalibración/fuga
				</p>
			</div>
		</div>

		<!-- KPI 4: Lotes con Anomalía Metrológica -->
		<div class="column is-12-mobile is-6-tablet is-3-desktop">
			<div class="card kpi-card p-4">
				<div class="level is-mobile mb-2">
					<div class="level-left">
						<span class="tag is-danger is-light has-text-weight-bold">Alerta Metrológica</span>
					</div>
					<div class="level-right">
						<span class="icon has-text-danger">
							<i class="fa-solid fa-gauge-high"></i>
						</span>
					</div>
				</div>
				<p class="is-size-7 has-text-grey mb-1">Lotes con Anomalía Metrológica</p>
				<h2 class="title is-4 mb-1 {resumen.lotes_con_anomalia > 0 ? 'has-text-danger' : 'has-text-success'}">
					{resumen.lotes_con_anomalia} de {resumen.total_lotes} lotes
				</h2>
				<p class="is-size-7 has-text-grey">
					<i class="fa-solid fa-sliders mr-1 {resumen.lotes_con_anomalia > 0 ? 'has-text-danger' : 'has-text-success'}"></i>
					{((resumen.lotes_con_anomalia / (resumen.total_lotes || 1)) * 100).toFixed(0)}% de lotes fuera de tolerancia
				</p>
			</div>
		</div>
	</div>

	<!-- SECCIÓN 3: GRÁFICA COMPARATIVA DE MERMAS POR LOTE EN LAYERCHART -->
	<div class="card mb-5 p-4" style="border-radius: 10px; border: 1px solid #cbd5e1;">
		<div class="level is-mobile mb-3" style="flex-wrap: wrap; gap: 0.5rem;">
			<div class="level-left">
				<div>
					<h3 class="title is-5 mb-0">
						<i class="fa-solid fa-chart-area mr-2 has-text-danger"></i>
						Curva de Mermas de Materia Prima por Lote vs. Tolerancia Contable
					</h3>
					<p class="is-size-7 has-text-grey">
						Visualización industrial con LayerChart: trazo de merma real (%) y umbral contable máximo admisible (Rule y = 1.5%)
					</p>
				</div>
			</div>
			<div class="level-right">
				<div class="tags are-small">
					<span class="tag is-danger is-light">
						<span class="legend-color-box mr-1" style="background:#dc2626;"></span>
						Merma Real por Lote (%)
					</span>
					<span class="tag is-warning is-light">
						<span class="legend-color-box mr-1" style="background:#d97706; border-top: 2px dashed #d97706;"></span>
						Tolerancia Máx. ERP (Rule y = 1.5%)
					</span>
					<span class="tag is-light">
						8 Lotes Auditados
					</span>
				</div>
			</div>
		</div>

		<!-- Contenedor Oficial LayerChart (.layerchart-box) -->
		<div class="layerchart-box" style="height: 300px;">
			{#if serieChart.length > 0}
				<Chart
					data={serieChart}
					x="idx"
					y="merma_real_pct"
					xScale={scaleLinear()}
					yScale={scaleLinear()}
					yDomain={[0, maxMerma]}
					padding={{ top: 20, right: 25, bottom: 35, left: 55 }}
				>
					<Svg>
						<Axis placement="left" grid rule format={(d) => `${d.toFixed(1)}%`} />
						<Axis
							placement="bottom"
							rule
							format={(d) => {
								const pt = serieChart.find((p) => p.idx === d);
								return pt ? pt.lote_id.replace('LOT-2026-', 'L-') : `L${d}`;
							}}
						/>
						<Area style="fill: rgba(220, 38, 38, 0.12);" />
						<Spline style="stroke: #dc2626; stroke-width: 2.5px;" />
						<Rule
							y={1.5}
							style="stroke: #d97706; stroke-width: 2px; stroke-dasharray: 4,4;"
						/>
					</Svg>
				</Chart>
			{:else}
				<div class="is-flex is-justify-content-center is-align-items-center" style="height: 100%;">
					<p class="has-text-grey">Sin datos de serie para graficar.</p>
				</div>
			{/if}
		</div>

		<div class="notification is-light p-3 mt-3 is-size-7" style="background: #f8fafc; border: 1px solid #e2e8f0;">
			<div class="columns is-vcentered">
				<div class="column is-8">
					<i class="fa-solid fa-circle-info has-text-info mr-1"></i>
					<strong>Interpretación de la Regla Contable:</strong> Los puntos que sobrepasan la línea discontinua ámbar
					(<code>&lt;Rule y={'{'}1.5{'}'} /&gt;</code>) no pueden ser absorbidos contablemente como merma operativa normal
					y son categorizados como <em>Desvío Auditable No Justificado</em>, activando el protocolo de bloqueo en ERP y recalibración metrológica.
				</div>
				<div class="column is-4 has-text-right-tablet">
					<span class="has-text-weight-bold has-text-danger">
						Desvío Acumulado: {formatearGuaranies(resumen.desvio_auditable_no_justificado_gs)}
					</span>
				</div>
			</div>
		</div>
	</div>

	<!-- SECCIÓN 4: TABLA DE CONCILIACIÓN DE LOTES Y PANEL DE DICTAMEN -->
	<div class="columns is-multiline mb-5">
		<!-- COLUMNA IZQUIERDA: TABLA Y FILTROS POR ESTADO -->
		<div class="column is-12-tablet is-8-desktop">
			<div class="card p-4" style="border-radius: 10px; border: 1px solid #cbd5e1; height: 100%;">
				<div class="level is-mobile mb-3" style="flex-wrap: wrap; gap: 0.5rem;">
					<div class="level-left">
						<div>
							<h3 class="title is-5 mb-0">
								<i class="fa-solid fa-list-check mr-2 has-text-link"></i>
								Lotes Industriales Cerrados en Planta
							</h3>
							<p class="is-size-7 has-text-grey">
								Balance de masa físico (caudalímetro MES) vs. contabilidad (remisión ERP)
							</p>
						</div>
					</div>
					<div class="level-right">
						<span class="tag is-dark is-light">
							{lotes.length} lotes mostrados
						</span>
					</div>
				</div>

				<!-- Filtros por Estado mediante URL SearchParams -->
				<div class="tabs is-toggle is-small is-fullwidth mb-3">
					<ul>
						<li class={estadoFiltroActivo === 'TODOS' ? 'is-active' : ''}>
							<a href="?estado=TODOS">
								<i class="fa-solid fa-globe mr-1"></i>
								<span>TODOS ({conciliacion.serie_lotes_chart?.length || 8})</span>
							</a>
						</li>
						<li class={estadoFiltroActivo === 'PENDIENTE' ? 'is-active' : ''}>
							<a href="?estado=PENDIENTE">
								<i class="fa-solid fa-clock mr-1 has-text-warning"></i>
								<span>PENDIENTE</span>
							</a>
						</li>
						<li class={estadoFiltroActivo === 'APROBADO_CONFORME' ? 'is-active' : ''}>
							<a href="?estado=APROBADO_CONFORME">
								<i class="fa-solid fa-check mr-1 has-text-success"></i>
								<span>CONFORME</span>
							</a>
						</li>
						<li class={estadoFiltroActivo === 'BLOQUEADO_RECALIBRACION' ? 'is-active' : ''}>
							<a href="?estado=BLOQUEADO_RECALIBRACION">
								<i class="fa-solid fa-lock mr-1 has-text-danger"></i>
								<span>BLOQUEADO</span>
							</a>
						</li>
						<li class={estadoFiltroActivo === 'ANOMALIA' ? 'is-active' : ''}>
							<a href="?estado=ANOMALIA">
								<i class="fa-solid fa-triangle-exclamation mr-1 has-text-danger"></i>
								<span>ANOMALÍA ({resumen.lotes_con_anomalia})</span>
							</a>
						</li>
					</ul>
				</div>

				<!-- Tabla Responsiva de Lotes -->
				<div class="table-container mb-2">
					<table class="table is-fullwidth is-striped is-hoverable is-narrow is-size-7">
						<thead>
							<tr style="background: #f1f5f9;">
								<th>ID Lote</th>
								<th>Producto</th>
								<th class="has-text-right">Masa ERP</th>
								<th class="has-text-right">Masa MES</th>
								<th class="has-text-right">Envasado</th>
								<th class="has-text-right">Merma</th>
								<th class="has-text-right">Pérdida (₲)</th>
								<th>Instrumento Sospechoso</th>
								<th>Estado</th>
								<th class="has-text-centered">Acción</th>
							</tr>
						</thead>
						<tbody>
							{#each lotes as lote (lote.lote_id)}
								<tr class={loteSeleccionadoId === lote.lote_id ? 'is-selected-row' : ''}>
									<td class="has-text-weight-bold">
										<code>{lote.lote_id}</code>
									</td>
									<td>
										<div class="has-text-weight-semibold">{lote.producto}</div>
										<span class="has-text-grey is-size-7">{lote.fecha_cierre}</span>
									</td>
									<td class="has-text-right font-mono">
										{Number(lote.masa_erp_almacen_kg).toLocaleString('es-PY')} kg
									</td>
									<td class="has-text-right font-mono">
										{Number(lote.masa_mes_caudalimetro_kg).toLocaleString('es-PY')} kg
									</td>
									<td class="has-text-right font-mono">
										{Number(lote.masa_producto_final_kg).toLocaleString('es-PY')} kg
									</td>
									<td class="has-text-right font-mono">
										{#if lote.merma_real_pct > (lote.merma_tolerada_pct || 1.5)}
											<span class="tag is-danger is-light has-text-weight-bold">
												{lote.merma_real_pct.toFixed(2)}%
											</span>
										{:else}
											<span class="tag is-success is-light">
												{lote.merma_real_pct.toFixed(2)}%
											</span>
										{/if}
									</td>
									<td class="has-text-right font-mono">
										<div class="has-text-weight-semibold">
											{formatearGuaranies(lote.perdida_merma_total_gs)}
										</div>
										{#if lote.desvio_sobre_tolerancia_gs > 0}
											<div class="is-size-7 has-text-danger">
												+{formatearGuaranies(lote.desvio_sobre_tolerancia_gs)}
											</div>
										{/if}
									</td>
									<td>
										{#if lote.sensor_sospechoso && !lote.sensor_sospechoso.startsWith('Ninguno')}
											<span class="tag is-warning is-light is-size-7" title={lote.sensor_sospechoso}>
												<i class="fa-solid fa-microchip mr-1"></i>
												{lote.sensor_sospechoso.length > 24
													? lote.sensor_sospechoso.slice(0, 22) + '...'
													: lote.sensor_sospechoso}
											</span>
										{:else}
											<span class="has-text-grey-light is-size-7">Nominal</span>
										{/if}
									</td>
									<td>
										{#if lote.estado_auditoria === 'APROBADO_CONFORME'}
											<span class="tag is-success is-light">
												<i class="fa-solid fa-check mr-1"></i> Conforme
											</span>
										{:else if lote.estado_auditoria === 'BLOQUEADO_RECALIBRACION'}
											<span class="tag is-danger is-light">
												<i class="fa-solid fa-ban mr-1"></i> Bloqueado
											</span>
										{:else}
											<span class="tag is-warning is-light">
												<i class="fa-solid fa-clock mr-1"></i> Pendiente
											</span>
										{/if}
									</td>
									<td class="has-text-centered">
										<button
											class="button is-small {loteSeleccionadoId === lote.lote_id ? 'is-link' : 'is-light'}"
											onclick={() => seleccionarLote(lote)}
											title="Cargar lote en el panel de dictamen"
										>
											<i class="fa-solid fa-gavel mr-1"></i>
											Auditar
										</button>
									</td>
								</tr>
							{:else}
								<tr>
									<td colspan="10" class="has-text-centered p-4 has-text-grey">
										No hay lotes con el filtro <code>{estadoFiltroActivo}</code>.
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>

				<div class="is-size-7 has-text-grey">
					<i class="fa-solid fa-lightbulb mr-1 has-text-warning"></i>
					Haga clic en <strong>Auditar</strong> en cualquier fila para cargar sus datos y emitir dictamen formal.
				</div>
			</div>
		</div>

		<!-- COLUMNA DERECHA: PANEL DE DICTAMEN DE AUDITORÍA CON USE:ENHANCE -->
		<div class="column is-12-tablet is-4-desktop">
			<div class="card p-4" style="border-radius: 10px; border: 1px solid #cbd5e1; background: #ffffff;">
				<div class="level is-mobile mb-3">
					<div class="level-left">
						<div>
							<h3 class="title is-5 mb-0">
								<i class="fa-solid fa-gavel mr-2 has-text-link"></i>
								Dictamen de Auditoría
							</h3>
							<p class="is-size-7 has-text-grey">Resolución Financiera y Metrológica</p>
						</div>
					</div>
					<div class="level-right">
						{#if loteSeleccionado}
							<span class="tag is-link is-light has-text-weight-bold">
								{loteSeleccionado.lote_id}
							</span>
						{/if}
					</div>
				</div>

				{#if loteSeleccionado}
					<!-- Ficha Rápida del Lote Seleccionado -->
					<div class="box p-3 mb-3" style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;">
						<div class="level is-mobile mb-1">
							<span class="is-size-7 has-text-weight-semibold">{loteSeleccionado.producto}</span>
							<span class="tag {loteSeleccionado.merma_real_pct > 1.5 ? 'is-danger' : 'is-success'} is-light is-size-7">
								Merma: {loteSeleccionado.merma_real_pct.toFixed(2)}%
							</span>
						</div>
						<div class="is-size-7 has-text-grey mb-1">
							Fecha Cierre: <code>{loteSeleccionado.fecha_cierre}</code>
						</div>
						<div class="columns is-mobile is-multiline is-gapless is-size-7 mb-0">
							<div class="column is-6">
								<span class="has-text-grey">Pérdida Total:</span><br />
								<strong class="has-text-danger-dark">
									{formatearGuaranies(loteSeleccionado.perdida_merma_total_gs)}
								</strong>
							</div>
							<div class="column is-6">
								<span class="has-text-grey">Desvío No Justif.:</span><br />
								<strong class="has-text-danger">
									{formatearGuaranies(loteSeleccionado.desvio_sobre_tolerancia_gs)}
								</strong>
							</div>
						</div>
						{#if loteSeleccionado.sensor_sospechoso && !loteSeleccionado.sensor_sospechoso.startsWith('Ninguno')}
							<div class="notification is-warning is-light p-2 mt-2 mb-0 is-size-7">
								<i class="fa-solid fa-triangle-exclamation mr-1"></i>
								<strong>Alerta:</strong> {loteSeleccionado.sensor_sospechoso}
							</div>
						{/if}
					</div>

					<!-- Formulario de Dictamen con SvelteKit Form Actions + use:enhance -->
					<form
						method="POST"
						action="?/emitirDictamen"
						use:enhance={() => {
							enviandoDictamen = true;
							return async ({ update }) => {
								await update();
								enviandoDictamen = false;
							};
						}}
					>
						<input type="hidden" name="lote_id" value={loteSeleccionado.lote_id} />

						<!-- Decisión / Acción del Dictamen -->
						<div class="field mb-3">
							<label class="label is-small" for="dictamen-accion">Dictamen y Acción Requerida</label>
							<div class="control has-icons-left">
								<div class="select is-small is-fullwidth">
									<select id="dictamen-accion" name="accion" bind:value={accionDictamen} required>
										<option value="BLOQUEADO_RECALIBRACION">
											BLOQUEADO: Ordenar Recalibración Metrológica
										</option>
										<option value="APROBADO_CONFORME">
											APROBADO CONFORME: Liberar Lote a Almacén ERP
										</option>
									</select>
								</div>
								<span class="icon is-small is-left">
									<i class="fa-solid fa-stamp"></i>
								</span>
							</div>
						</div>

						<!-- Auditor Firmante -->
						<div class="field mb-3">
							<label class="label is-small" for="dictamen-auditor">Auditor Contable-Metrológico Firmante</label>
							<div class="control has-icons-left">
								<input
									id="dictamen-auditor"
									class="input is-small"
									type="text"
									name="auditor"
									bind:value={auditorNombre}
									required
									placeholder="Nombre y cargo del auditor"
								/>
								<span class="icon is-small is-left">
									<i class="fa-solid fa-user-tie"></i>
								</span>
							</div>
						</div>

						<!-- Causa Raíz Detectada -->
						<div class="field mb-3">
							<label class="label is-small" for="dictamen-causa">Causa Raíz Diagnosticada</label>
							<div class="control has-icons-left">
								<input
									id="dictamen-causa"
									class="input is-small"
									type="text"
									name="causa_raiz"
									bind:value={causaRaiz}
									required
									placeholder="Ej: Deriva en celda de carga de silo"
								/>
								<span class="icon is-small is-left">
									<i class="fa-solid fa-magnifying-glass"></i>
								</span>
							</div>
						</div>

						<!-- Observaciones y Medidas Correctivas -->
						<div class="field mb-4">
							<label class="label is-small" for="dictamen-observacion">Observación y Justificación Técnica</label>
							<div class="control">
								<textarea
									id="dictamen-observacion"
									class="textarea is-small"
									name="observacion"
									rows="3"
									bind:value={observacion}
									required
									placeholder="Detalle la fundamentación técnica y contable del dictamen..."
								></textarea>
							</div>
						</div>

						<div class="field">
							<button
								type="submit"
								class="button is-link is-fullwidth has-text-weight-bold {enviandoDictamen ? 'is-loading' : ''}"
							>
								<i class="fa-solid fa-file-signature mr-2"></i>
								Emitir Dictamen en FastAPI
							</button>
						</div>
					</form>

					<!-- Detalle del Último Dictamen Registrado en FastAPI -->
					{#if loteSeleccionado.dictamen_auditor}
						<div class="box p-3 mt-3 is-size-7" style="background: #f1f5f9; border-left: 4px solid #2563eb;">
							<div class="has-text-weight-semibold mb-1">
								<i class="fa-solid fa-file-contract mr-1 has-text-link"></i>
								Dictamen Previo en Memoria:
							</div>
							<p class="mb-1">{loteSeleccionado.dictamen_auditor}</p>
							<span class="has-text-grey">
								Firmado por: <strong>{loteSeleccionado.auditor_firmante || 'Sistema Automático'}</strong>
							</span>
						</div>
					{/if}
				{:else}
					<p class="has-text-grey is-size-7">Seleccione un lote para auditar.</p>
				{/if}
			</div>
		</div>
	</div>
{/if}

<!-- SECCIÓN 5: VISOR PEDAGÓGICO DE CÓDIGO FUENTE -->
<CodeViewer
	titulo="Código Fuente — Proyecto 8: Conciliación Contable de Lotes (MES vs. ERP)"
	archivos={[
		{
			nombre: '+page.server.js (BFF SSR y Form Actions)',
			descripcion: 'Carga inmutable de lotes mediante SSR y Form Action emitirDictamen conectada a FastAPI sin recargar la página.',
			codigo: codigoServerJs
		},
		{
			nombre: '+page.svelte (Runes Svelte 5 + LayerChart)',
			descripcion: 'Visualización de mermas con LayerChart y Rule horizontal en 1.5%, KPIs en Guaraníes y tabla reactiva.',
			codigo: codigoSvelteJs
		},
		{
			nombre: 'FastAPI main.py (/api/admin/conciliacion-lotes)',
			descripcion: 'Endpoints en Python: balance de masa físico vs. fiscal, cálculo de desvíos en ₲ y registro auditado de dictámenes.',
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

	.kpi-danger {
		background: linear-gradient(180deg, #ffffff 0%, #fef2f2 100%);
		border-color: #fca5a5;
	}

	.kpi-warning {
		background: linear-gradient(180deg, #ffffff 0%, #fffbeb 100%);
		border-color: #fde68a;
	}

	.legend-color-box {
		display: inline-block;
		width: 14px;
		height: 10px;
		border-radius: 2px;
		vertical-align: middle;
	}

	.is-selected-row {
		background-color: #eff6ff !important;
		outline: 2px solid #3b82f6;
	}

	.font-mono {
		font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
	}
</style>
