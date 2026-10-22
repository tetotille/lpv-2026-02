<script>
	/**
	 * +page.svelte - Proyecto 6 (Admin 2):
	 * Auditoría Energética y Pliego Tarifario ANDE (Horario Punta vs. Fuera de Punta y Penalización cos φ)
	 *
	 * Cátedra: Lenguajes de Programación Visual — FIUNA
	 * Svelte 5 Runes ($props, $state, $derived, $effect)
	 * 100% dependiente de FastAPI (http://localhost:8007)
	 */

	import { enhance } from '$app/forms';
	import { FASTAPI_BASE_URL } from '$lib/config.js';
	import { formatearGuaranies, formatearMillonesGuaranies } from '$lib/utils/moneda.js';
	import { Chart, Svg, Spline, Area, Axis, Rule } from 'layerchart';
	import { scaleLinear } from 'd3-scale';
	import CodeViewer from '$lib/components/CodeViewer.svelte';

	let { data, form } = $props();

	// Estado reactivo del formulario de simulación
	let formCosPhi = $state(0.96);
	let formPctDesplazamiento = $state(35.0);
	let formInversionGs = $state(95000000);
	let isSimulating = $state(false);
	let mensajeFeedback = $state(null);

	// Datos derivados desde FastAPI (SSR o Form Action simulacion)
	const datosAnde = $derived(form?.simulacion || data.datosAnde || null);
	const pliego = $derived(datosAnde?.pliego_ande || null);
	const situacionActual = $derived(datosAnde?.situacion_actual || null);
	const ultimaSimulacion = $derived(datosAnde?.ultima_simulacion || null);
	const curvaHoraria = $derived(datosAnde?.curva_horaria_24h || []);

	// Sincronizar inputs si FastAPI retorna nuevos parámetros por defecto
	$effect(() => {
		if (ultimaSimulacion) {
			formCosPhi = Number(ultimaSimulacion.cos_phi_objetivo ?? 0.96);
			formPctDesplazamiento = Number(ultimaSimulacion.pct_desplazamiento_punta ?? 35.0);
			formInversionGs = Number(ultimaSimulacion.inversion_capacitores_gs ?? 95000000);
		}
	});

	// Cálculo de pico máximo para el eje Y de LayerChart
	const maxKw = $derived.by(() => {
		if (!curvaHoraria || curvaHoraria.length === 0) return 600;
		let maxVal = 0;
		for (const d of curvaHoraria) {
			if (d.kw_actual > maxVal) maxVal = d.kw_actual;
			if (d.kw_optimizado > maxVal) maxVal = d.kw_optimizado;
		}
		return Math.ceil(maxVal * 1.15);
	});

	// Presets de inversión en banco de capacitores
	const presetCapacitores = [
		{ label: 'Banco 150 kVAr (Estándar)', valor: 65000000 },
		{ label: 'Banco 250 kVAr (Filtros Armónicos)', valor: 95000000 },
		{ label: 'Banco 400 kVAr (Tiristores Rápidos)', valor: 135000000 }
	];

	// Código fuente pedagógico para CodeViewer
	const archivosCodigo = [
		{
			nombre: '+page.server.js',
			descripcion: 'SSR Backend-For-Frontend que consulta FastAPI y procesa Form Action con validación.',
			codigo: `import { FASTAPI_BASE_URL } from '$lib/config.js';
import { fail } from '@sveltejs/kit';

export async function load({ fetch }) {
    try {
        const res = await fetch(\`\${FASTAPI_BASE_URL}/api/admin/energia-ande\`);
        if (!res.ok) return { fastapiOnline: false, errorConexion: 'FastAPI respondió con error HTTP ' + res.status };
        return {
            fastapiOnline: true,
            endpointConsultado: \`\${FASTAPI_BASE_URL}/api/admin/energia-ande\`,
            datosAnde: await res.json()
        };
    } catch (err) {
        return { fastapiOnline: false, errorConexion: 'No se pudo conectar con FastAPI (:8007)' };
    }
}

export const actions = {
    simularTarifa: async ({ request, fetch }) => {
        const fd = await request.formData();
        const res = await fetch(\`\${FASTAPI_BASE_URL}/api/admin/energia-ande/simular\`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                cos_phi_objetivo: Number(fd.get('cos_phi_objetivo')),
                pct_desplazamiento_punta: Number(fd.get('pct_desplazamiento_punta')),
                inversion_capacitores_gs: Number(fd.get('inversion_capacitores_gs'))
            })
        });
        if (!res.ok) return fail(res.status, { error: 'Error al simular en FastAPI' });
        return { success: true, simulacion: await res.json() };
    }
};`
		},
		{
			nombre: '+page.svelte',
			descripcion: 'Interfaz reactiva Svelte 5 con LayerChart, sliders de optimización y use:enhance.',
			codigo: `<script>
    import { enhance } from '$app/forms';
    import { formatearGuaranies } from '$lib/utils/moneda.js';
    import { Chart, Svg, Spline, Area, Axis, Rule } from 'layerchart';
    import { scaleLinear } from 'd3-scale';

    let { data, form } = $props();
    let formCosPhi = $state(0.96);
    let formPctDesplazamiento = $state(35.0);
    let formInversionGs = $state(95000000);

    const datosAnde = $derived(form?.simulacion || data.datosAnde);
<\/script>`
		},
		{
			nombre: 'backend_fastapi/main.py',
			descripcion: 'Motor matemático del Pliego Tarifario ANDE N° 21 en Python FastAPI.',
			codigo: `@app.get("/api/admin/energia-ande")
async def get_energia_ande():
    return calcular_auditoria_ande(
        cos_phi_obj=simulacion_ande_activa["cos_phi_objetivo"],
        pct_desp=simulacion_ande_activa["pct_desplazamiento_punta"],
        inv_capacitores=simulacion_ande_activa["inversion_capacitores_gs"]
    )

@app.post("/api/admin/energia-ande/simular")
async def simular_energia_ande(payload: SimularEnergiaAndeRequest):
    # Recalcula curvas de 24 horas y penalización reactiva ANDE
    # Multa reactiva: 4% por cada centésimo debajo de cos phi 0.92
    if payload.cos_phi_objetivo < 0.92:
        recargo_pct = (0.92 - payload.cos_phi_objetivo) * 100.0 * 4.0
    else:
        recargo_pct = 0.0
    ...`
		}
	];
</script>

<svelte:head>
	<title>Auditoría Energética ANDE (₲) | LPV FIUNA</title>
</svelte:head>

<div class="container py-5 px-3">
	<!-- ENCABEZADO Y CONTEXTO DEL PLIEGO TARIFARIO ANDE -->
	<div class="level mb-4">
		<div class="level-left">
			<div>
				<div class="is-flex is-align-items-center" style="gap: 0.6rem;">
					<span class="tag is-warning is-medium">
						<i class="fa-solid fa-bolt has-text-dark"></i>
					</span>
					<h1 class="title is-4 mb-0">Auditoría Energética y Pliego Tarifario ANDE</h1>
					<span class="tag is-dark is-family-code">Proyecto 6 (Admin 2)</span>
				</div>
				<p class="subtitle is-6 has-text-grey mt-1 mb-0">
					Media Tensión (23 kV) · Gestión de Demanda en Horario Punta (18:00–22:00 hs) y Compensación cos φ
				</p>
			</div>
		</div>

		<div class="level-right">
			<div class="tags has-addons mb-0">
				<span class="tag is-dark is-family-code">FastAPI :8007</span>
				{#if data.fastapiOnline}
					<span class="tag is-success has-text-weight-bold">
						<i class="fa-solid fa-circle-check mr-1"></i> ONLINE
					</span>
				{:else}
					<span class="tag is-danger has-text-weight-bold">
						<i class="fa-solid fa-plug-circle-xmark mr-1"></i> DESCONECTADO
					</span>
				{/if}
			</div>
		</div>
	</div>

	<!-- ALERTA SI FASTAPI ESTÁ OFFLINE -->
	{#if !data.fastapiOnline}
		<div class="notification is-danger is-light mb-5" style="border-left: 5px solid #ef4444;">
			<div class="is-flex is-align-items-center">
				<i class="fa-solid fa-triangle-exclamation fa-2x mr-3 has-text-danger"></i>
				<div>
					<h4 class="title is-6 mb-1 has-text-danger-dark">Servidor FastAPI Desconectado (:8007)</h4>
					<p class="is-size-7 mb-2">
						{data.errorConexion || 'No se pudo consultar el endpoint http://localhost:8007/api/admin/energia-ande.'}
					</p>
					<p class="is-size-7 has-text-grey">
						Inicia el backend ejecutando en la terminal:
						<code class="has-text-weight-bold">cd backend_fastapi && /home/tetotille/.venv/bin/uvicorn main:app --port 8007 --reload</code>
					</p>
				</div>
			</div>
		</div>
	{/if}

	<!-- NOTA DE CONTEXTO TÉCNICO REGULATORIO ANDE -->
	<div class="card mb-5" style="border-radius: 8px; border: 1px solid #e2e8f0;">
		<div class="card-content py-3 px-4">
			<div class="columns is-vcentered">
				<div class="column is-8">
					<div class="is-flex is-align-items-start" style="gap: 0.75rem;">
						<i class="fa-solid fa-scale-balanced has-text-link mt-1"></i>
						<div>
							<h3 class="title is-6 mb-1">
								Marco Regulatorio ANDE · Pliego Tarifario N° 21 (Grupo Media Tensión 23 kV)
							</h3>
							<p class="is-size-7 has-text-grey-dark">
								En Paraguay, las industrias en Media Tensión pagan <strong>{formatearGuaranies(pliego?.tarifa_punta_gs_kwh ?? 685)}/kWh</strong> en el
								<strong>Horario de Punta de Carga (18:00 a 22:00 hs)</strong> frente a <strong>{formatearGuaranies(pliego?.tarifa_fuera_punta_gs_kwh ?? 310)}/kWh</strong> fuera de punta
								(más de 2.2× de sobrecosto), sumado a <strong>{formatearGuaranies(pliego?.cargo_potencia_punta_gs_kw ?? 41500)}/kW-mes</strong> por potencia reservada.
								Además, operar con un <strong>Factor de Potencia cos φ &lt; 0.92</strong> activa un recargo sancionatorio del <strong>4% sobre el total de la factura</strong> por cada centésimo inferior.
							</p>
						</div>
					</div>
				</div>

				<div class="column is-4 has-text-right-tablet">
					<div class="is-inline-block has-text-left p-2" style="background-color: #f8fafc; border-radius: 6px; border: 1px dashed #cbd5e1;">
						<div class="is-size-7">
							<span class="has-text-grey">Endpoint activo:</span><br>
							<code class="is-size-7 has-text-link">{data.endpointConsultado || `${FASTAPI_BASE_URL}/api/admin/energia-ande`}</code>
						</div>
					</div>
				</div>
			</div>
		</div>
	</div>

	{#if datosAnde && situacionActual && ultimaSimulacion}
		<!-- RESUMEN FINANCIERO EJECUTIVO-CONTABLE (DATOS FASTAPI) -->
		<div class="columns is-multiline mb-4">
			<!-- SITUACIÓN ACTUAL CON PENALIZACIÓN -->
			<div class="column is-12-mobile is-6-tablet is-3-desktop">
				<div class="card p-4 has-background-danger-light" style="border: 1px solid #fca5a5; border-radius: 8px; height: 100%;">
					<div class="is-flex is-justify-content-space-between is-align-items-center mb-1">
						<span class="is-size-7 has-text-weight-bold has-text-danger-dark">FACTURA MENSUAL ACTUAL</span>
						<span class="tag is-danger is-small">Sin Optimizar</span>
					</div>
					<h2 class="title is-4 has-text-danger-dark mb-1">
						{formatearGuaranies(situacionActual.factura_total_mensual_gs)}
					</h2>
					<p class="is-size-7 has-text-danger">
						<i class="fa-solid fa-triangle-exclamation mr-1"></i>
						Incluye multa reactiva de <strong>{formatearGuaranies(situacionActual.multa_reactiva_gs)}</strong>
						(cos φ = {situacionActual.cos_phi_actual}, recargo del <strong>+{situacionActual.recargo_reactiva_pct}%</strong>).
					</p>
					<hr class="my-2" style="background-color: #fca5a5; height: 1px;">
					<div class="is-size-7 has-text-grey-dark">
						<div>Energía base: <strong>{formatearGuaranies(situacionActual.costo_energia_base_gs)}</strong></div>
						<div>Potencia ({situacionActual.demanda_maxima_punta_kw} kW): <strong>{formatearGuaranies(situacionActual.costo_potencia_gs)}</strong></div>
					</div>
				</div>
			</div>

			<!-- SITUACIÓN OPTIMIZADA CON FASTAPI -->
			<div class="column is-12-mobile is-6-tablet is-3-desktop">
				<div class="card p-4 has-background-success-light" style="border: 1px solid #86efac; border-radius: 8px; height: 100%;">
					<div class="is-flex is-justify-content-space-between is-align-items-center mb-1">
						<span class="is-size-7 has-text-weight-bold has-text-success-dark">FACTURA MENSUAL OPTIMIZADA</span>
						<span class="tag is-success is-small">Simulada FastAPI</span>
					</div>
					<h2 class="title is-4 has-text-success-dark mb-1">
						{formatearGuaranies(ultimaSimulacion.nueva_factura_mensual_gs)}
					</h2>
					<p class="is-size-7 has-text-success-dark">
						<i class="fa-solid fa-circle-check mr-1"></i>
						Multa reactiva eliminada: <strong>{formatearGuaranies(ultimaSimulacion.nueva_multa_reactiva_gs)}</strong>
						(cos φ obj = {ultimaSimulacion.cos_phi_objetivo}).
					</p>
					<hr class="my-2" style="background-color: #86efac; height: 1px;">
					<div class="is-size-7 has-text-grey-dark">
						<div>Ahorro mensual: <strong class="has-text-success-dark">+{formatearGuaranies(ultimaSimulacion.ahorro_mensual_gs)}</strong></div>
						<div>Desplazamiento punta: <strong>{ultimaSimulacion.pct_desplazamiento_punta}%</strong></div>
					</div>
				</div>
			</div>

			<!-- AHORRO ANUAL PROYECTADO -->
			<div class="column is-12-mobile is-6-tablet is-3-desktop">
				<div class="card p-4 has-background-info-light" style="border: 1px solid #93c5fd; border-radius: 8px; height: 100%;">
					<div class="is-flex is-justify-content-space-between is-align-items-center mb-1">
						<span class="is-size-7 has-text-weight-bold has-text-info-dark">AHORRO NETO ANUAL</span>
						<span class="tag is-info is-small">Flujo de Caja</span>
					</div>
					<h2 class="title is-4 has-text-info-dark mb-1">
						{formatearGuaranies(ultimaSimulacion.ahorro_anual_gs)}
					</h2>
					<p class="is-size-7 has-text-info-dark">
						Equivalente a <strong>{formatearMillonesGuaranies(ultimaSimulacion.ahorro_anual_gs)}</strong> liberados al año para reinversión operativa mecatrónica.
					</p>
					<hr class="my-2" style="background-color: #93c5fd; height: 1px;">
					<div class="is-size-7 has-text-grey-dark">
						<div>Impacto mensual: <strong>{formatearGuaranies(ultimaSimulacion.ahorro_mensual_gs)} / mes</strong></div>
						<div>Eficiencia tarifaria: <strong>+{((ultimaSimulacion.ahorro_mensual_gs / situacionActual.factura_total_mensual_gs) * 100).toFixed(1)}%</strong></div>
					</div>
				</div>
			</div>

			<!-- RETORNO DE INVERSIÓN (PAYBACK & ROI) -->
			<div class="column is-12-mobile is-6-tablet is-3-desktop">
				<div class="card p-4 has-background-warning-light" style="border: 1px solid #fde047; border-radius: 8px; height: 100%;">
					<div class="is-flex is-justify-content-space-between is-align-items-center mb-1">
						<span class="is-size-7 has-text-weight-bold has-text-warning-dark">RETORNO CAPEX (PAYBACK)</span>
						<span class="tag is-warning is-small">Capacitores</span>
					</div>
					<h2 class="title is-4 has-text-warning-dark mb-1">
						{ultimaSimulacion.payback_meses} meses
					</h2>
					<p class="is-size-7 has-text-warning-dark">
						ROI anual: <strong>{ultimaSimulacion.roi_anual_pct}%</strong> sobre inversión de
						<strong>{formatearGuaranies(ultimaSimulacion.inversion_capacitores_gs)}</strong>.
					</p>
					<hr class="my-2" style="background-color: #fde047; height: 1px;">
					<div class="is-size-7 has-text-grey-dark">
						<div>Amortización: <strong class="has-text-success-dark">Ultra-rápida (&lt; 4 meses)</strong></div>
						<div>Vida útil estimada: <strong>10 a 12 años</strong></div>
					</div>
				</div>
			</div>
		</div>

		<!-- PANEL PRINCIPAL: SIMULADOR Y GRÁFICA LAYERCHART -->
		<div class="columns is-multiline mb-5">
			<!-- FORMULARIO DE SIMULACIÓN TARIFARIA HACIA FASTAPI -->
			<div class="column is-12-tablet is-4-desktop">
				<div class="card p-4" style="border-radius: 8px; border: 1px solid #cbd5e1; height: 100%;">
					<div class="is-flex is-align-items-center mb-3" style="gap: 0.5rem;">
						<span class="tag is-link is-medium">
							<i class="fa-solid fa-sliders"></i>
						</span>
						<div>
							<h3 class="title is-6 mb-0">Simulador de Optimización ANDE</h3>
							<p class="is-size-7 has-text-grey">Ejecuta cálculos en FastAPI (:8007)</p>
						</div>
					</div>

					{#if mensajeFeedback}
						<div class="notification is-{mensajeFeedback.tipo} is-light p-2 mb-3 is-size-7">
							<button type="button" class="delete is-small" onclick={() => (mensajeFeedback = null)} aria-label="Cerrar"></button>
							{mensajeFeedback.texto}
						</div>
					{/if}

					<form
						method="POST"
						action="?/simularTarifa"
						use:enhance={() => {
							isSimulating = true;
							return async ({ result, update }) => {
								isSimulating = false;
								if (result.type === 'success') {
									mensajeFeedback = { tipo: 'success', texto: 'Simulación recalculada exitosamente en FastAPI.' };
									await update({ reset: false });
								} else if (result.type === 'failure') {
									mensajeFeedback = { tipo: 'danger', texto: result.data?.error || 'Error al ejecutar la simulación en FastAPI.' };
								}
							};
						}}
					>
						<!-- PARÁMETRO 1: FACTOR DE POTENCIA COS PHI -->
						<div class="field mb-4">
							<div class="is-flex is-justify-content-space-between is-align-items-center mb-1">
								<label class="label is-size-7 mb-0" for="cos_phi_input">
									<i class="fa-solid fa-gauge mr-1 has-text-info"></i> Factor de Potencia (cos φ)
								</label>
								<span class="tag {formCosPhi >= 0.92 ? 'is-success' : 'is-danger'} is-light is-size-7">
									{#if formCosPhi >= 0.92}
										<i class="fa-solid fa-check mr-1"></i> Conforme ANDE (0% multa)
									{:else}
										<i class="fa-solid fa-xmark mr-1"></i> Recargo +{((0.92 - formCosPhi) * 100 * 4).toFixed(0)}%
									{/if}
								</span>
							</div>
							<div class="is-flex is-align-items-center" style="gap: 0.5rem;">
								<input
									id="cos_phi_range"
									type="range"
									class="slider is-fullwidth"
									min="0.81"
									max="0.98"
									step="0.01"
									bind:value={formCosPhi}
									style="flex: 1;"
								/>
								<input
									id="cos_phi_input"
									type="number"
									name="cos_phi_objetivo"
									class="input is-small has-text-centered has-text-weight-bold"
									style="width: 75px;"
									min="0.81"
									max="0.98"
									step="0.01"
									bind:value={formCosPhi}
									required
								/>
							</div>
							<p class="help is-size-7 has-text-grey mt-1">
								Reglamentario ANDE: &ge; 0.92. Cada 0.01 inferior añade 4% de recargo.
							</p>
						</div>

						<!-- PARÁMETRO 2: DESPLAZAMIENTO DE CARGA EN HORARIO PUNTA (PEAK SHAVING) -->
						<div class="field mb-4">
							<div class="is-flex is-justify-content-space-between is-align-items-center mb-1">
								<label class="label is-size-7 mb-0" for="desp_input">
									<i class="fa-solid fa-clock-rotate-left mr-1 has-text-warning"></i> Desplazamiento Punta (18–22 hs)
								</label>
								<span class="tag is-info is-light is-size-7">
									{formPctDesplazamiento}% hacia madrugada
								</span>
							</div>
							<div class="is-flex is-align-items-center" style="gap: 0.5rem;">
								<input
									id="desp_range"
									type="range"
									class="slider is-fullwidth"
									min="0"
									max="60"
									step="5"
									bind:value={formPctDesplazamiento}
									style="flex: 1;"
								/>
								<input
									id="desp_input"
									type="number"
									name="pct_desplazamiento_punta"
									class="input is-small has-text-centered has-text-weight-bold"
									style="width: 75px;"
									min="0"
									max="60"
									step="1"
									bind:value={formPctDesplazamiento}
									required
								/>
							</div>
							<p class="help is-size-7 has-text-grey mt-1">
								Desplaza molienda y hornos pesados a tarifa de 310 ₲/kWh (01:00–05:00 hs).
							</p>
						</div>

						<!-- PARÁMETRO 3: INVERSIÓN CAPEX EN CAPACITORES -->
						<div class="field mb-4">
							<label class="label is-size-7 mb-1" for="inv_input">
								<i class="fa-solid fa-coins mr-1 has-text-success"></i> Inversión Banco Capacitores (₲)
							</label>
							<div class="buttons are-small mb-2">
								{#each presetCapacitores as p}
									<button
										type="button"
										class="button {formInversionGs === p.valor ? 'is-link is-selected' : 'is-white'}"
										style="border: 1px solid #cbd5e1; font-size: 0.72rem;"
										onclick={() => (formInversionGs = p.valor)}
									>
										{p.label}
									</button>
								{/each}
							</div>
							<input
								id="inv_input"
								type="number"
								name="inversion_capacitores_gs"
								class="input is-small has-text-weight-bold"
								bind:value={formInversionGs}
								min="10000000"
								step="1000000"
								required
							/>
							<p class="help is-size-7 has-text-grey mt-1">
								Presupuesto CapEx: <strong>{formatearGuaranies(formInversionGs)}</strong>
							</p>
						</div>

						<!-- BOTÓN DE ENVÍO HACIA FASTAPI -->
						<button
							type="submit"
							class="button is-link is-fullwidth {isSimulating ? 'is-loading' : ''}"
							disabled={isSimulating || !data.fastapiOnline}
						>
							<i class="fa-solid fa-calculator mr-2"></i>
							{isSimulating ? 'Calculando en FastAPI...' : 'Simular en FastAPI (:8007)'}
						</button>
					</form>
				</div>
			</div>

			<!-- GRÁFICA DE PERFIL DE CARGA DE 24 HORAS EN LAYERCHART -->
			<div class="column is-12-tablet is-8-desktop">
				<div class="card p-4" style="border-radius: 8px; border: 1px solid #cbd5e1; height: 100%;">
					<div class="level mb-2">
						<div class="level-left">
							<div>
								<h3 class="title is-6 mb-0">
									<i class="fa-solid fa-chart-line mr-2 has-text-link"></i>
									Curva de Demanda de 24 Horas (kW) · Peak Shaving &amp; Load Shifting
								</h3>
								<p class="is-size-7 has-text-grey">
									Contraste de potencia en Horario Punta ANDE (18:00–22:00 hs) vs. redistribución en Valle
								</p>
							</div>
						</div>

						<div class="level-right">
							<div class="tags are-small mb-0">
								<span class="tag is-white" style="border: 1px solid #ef4444; color: #ef4444; font-weight: 600;">
									<span style="display: inline-block; width: 10px; height: 3px; background-color: #ef4444; margin-right: 5px;"></span>
									Demanda Actual
								</span>
								<span class="tag is-white" style="border: 1px solid #10b981; color: #10b981; font-weight: 600;">
									<span style="display: inline-block; width: 10px; height: 3px; background-color: #10b981; margin-right: 5px;"></span>
									Demanda Optimizada
								</span>
								<span class="tag is-danger is-light">
									<i class="fa-solid fa-fire mr-1"></i> Punta ANDE (18–22 hs)
								</span>
							</div>
						</div>
					</div>

					<!-- CONTENEDOR OFICIAL LAYERCHART (.layerchart-box) -->
					<div class="layerchart-box" style="height: 340px; position: relative;">
						{#if curvaHoraria.length > 0}
							<Chart
								data={curvaHoraria}
								x="hora"
								y="kw_actual"
								xScale={scaleLinear()}
								yScale={scaleLinear()}
								yDomain={[0, maxKw]}
								padding={{ top: 20, right: 30, bottom: 35, left: 60 }}
							>
								<Svg>
									<Axis placement="left" grid rule format={(d) => `${d} kW`} />
									<Axis
										placement="bottom"
										rule
										ticks={[0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 23]}
										format={(d) => `${String(d).padStart(2, '0')}:00`}
									/>

									<!-- Curva Demanda Actual (Roja) -->
									<Area y1="kw_actual" style="fill: rgba(239, 68, 68, 0.10);" />
									<Spline y="kw_actual" style="stroke: #ef4444; stroke-width: 2.5px;" />

									<!-- Curva Demanda Optimizada (Verde) -->
									<Area y1="kw_optimizado" style="fill: rgba(16, 185, 129, 0.15);" />
									<Spline y="kw_optimizado" style="stroke: #10b981; stroke-width: 2.5px;" />

									<!-- Línea de Demanda Máxima Contratada ANDE -->
									<Rule
										y={situacionActual.demanda_maxima_punta_kw}
										style="stroke: #dc2626; stroke-width: 1.5px; stroke-dasharray: 4,4;"
									/>
								</Svg>
							</Chart>
						{:else}
							<div class="is-flex is-justify-content-center is-align-items-center" style="height: 100%;">
								<p class="has-text-grey is-size-7">No hay datos de curva horaria disponibles desde FastAPI.</p>
							</div>
						{/if}
					</div>

					<!-- NOTA EXPLICATIVA AL PIE DE LA GRÁFICA -->
					<div class="notification is-light p-2 mt-2 is-size-7" style="background-color: #f8fafc; border-left: 3px solid #3b82f6;">
						<div class="columns is-mobile is-vcentered mb-0">
							<div class="column py-0">
								<i class="fa-solid fa-lightbulb has-text-warning mr-1"></i>
								<strong>Fenómeno Mecatrónico:</strong> Entre las <strong>18:00 y las 22:00 hs</strong>, la potencia se recorta en un
								<strong>{ultimaSimulacion.pct_desplazamiento_punta}%</strong> evitando la tarifa de 685 ₲/kWh y el cargo por potencia pico.
								Esa masa de molienda se desplaza a la franja de madrugada (<strong>01:00 a 05:00 hs</strong>), operando a 310 ₲/kWh.
							</div>
							<div class="column is-narrow py-0 has-text-right">
								<span class="tag is-white is-size-7" style="border: 1px solid #cbd5e1;">
									Demanda Pico: <strong>{situacionActual.demanda_maxima_punta_kw} kW</strong>
								</span>
							</div>
						</div>
					</div>
				</div>
			</div>
		</div>

		<!-- TABLA DETALLADA DE LAS 24 HORAS CON RESALTADO EN HORARIO PUNTA -->
		<div class="card mb-5" style="border-radius: 8px; border: 1px solid #cbd5e1; overflow: hidden;">
			<header class="card-header px-4 py-2" style="background-color: #f8fafc; border-bottom: 1px solid #e2e8f0;">
				<div class="card-header-title is-size-6 py-1">
					<i class="fa-solid fa-table-list mr-2 has-text-link"></i>
					Desglose Horario de Facturación y Potencia (24 Horas)
				</div>
				<span class="tag is-danger is-light has-text-weight-bold">
					Horas 18, 19, 20 y 21 resaltadas (Punta ANDE)
				</span>
			</header>

			<div class="table-container mb-0" style="max-height: 380px; overflow-y: auto;">
				<table class="table is-fullwidth is-striped is-hoverable is-narrow is-size-7 mb-0">
					<thead>
						<tr style="background-color: #f1f5f9; position: sticky; top: 0; z-index: 2;">
							<th class="has-text-centered">Hora</th>
							<th>Franja Pliego ANDE</th>
							<th class="has-text-right">Demanda Actual</th>
							<th class="has-text-right">Demanda Optimizada</th>
							<th class="has-text-right">Δ Desplazamiento</th>
							<th class="has-text-right">Costo Actual (₲)</th>
							<th class="has-text-right">Costo Optimizado (₲)</th>
							<th class="has-text-right">Ahorro Horario (₲)</th>
						</tr>
					</thead>
					<tbody>
						{#each curvaHoraria as row (row.hora)}
							{@const deltaKw = row.kw_actual - row.kw_optimizado}
							{@const ahorroHora = row.costo_hora_actual_gs - row.costo_hora_optimizado_gs}
							<tr
								style={row.es_horario_punta
									? 'background-color: #fef2f2; font-weight: 600;'
									: ''}
							>
								<td class="has-text-centered is-family-code">{row.etiqueta}</td>
								<td>
									{#if row.es_horario_punta}
										<span class="tag is-danger is-light has-text-weight-bold">
											<i class="fa-solid fa-fire mr-1"></i> PUNTA (685 ₲/kWh)
										</span>
									{:else}
										<span class="tag is-info is-light">
											VALLE / FUERA PUNTA (310 ₲/kWh)
										</span>
									{/if}
								</td>
								<td class="has-text-right is-family-code">{row.kw_actual.toFixed(1)} kW</td>
								<td class="has-text-right is-family-code has-text-success-dark">
									{row.kw_optimizado.toFixed(1)} kW
								</td>
								<td class="has-text-right is-family-code">
									{#if deltaKw > 0}
										<span class="has-text-success">-{deltaKw.toFixed(1)} kW</span>
									{:else if deltaKw < 0}
										<span class="has-text-info">+{Math.abs(deltaKw).toFixed(1)} kW</span>
									{:else}
										<span class="has-text-grey">0.0 kW</span>
									{/if}
								</td>
								<td class="has-text-right is-family-code">{formatearGuaranies(row.costo_hora_actual_gs)}</td>
								<td class="has-text-right is-family-code has-text-success-dark">
									{formatearGuaranies(row.costo_hora_optimizado_gs)}
								</td>
								<td class="has-text-right is-family-code">
									{#if ahorroHora > 0}
										<span class="has-text-success has-text-weight-bold">+{formatearGuaranies(ahorroHora)}</span>
									{:else if ahorroHora < 0}
										<span class="has-text-grey">{formatearGuaranies(ahorroHora)}</span>
									{:else}
										<span class="has-text-grey">₲ 0</span>
									{/if}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>
	{/if}

	<!-- VISOR DE CÓDIGO PEDAGÓGICO DE LA CÁTEDRA -->
	<CodeViewer
		titulo="Código Fuente de la Auditoría Tarifaria ANDE (SvelteKit + FastAPI)"
		archivos={archivosCodigo}
	/>
</div>

<style>
	/* Ajustes tipográficos para la vista administrativa */
	.is-family-code {
		font-family: 'JetBrains Mono', 'Fira Code', monospace;
	}
</style>
