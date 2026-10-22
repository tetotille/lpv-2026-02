<script>
	/**
	 * Proyecto 7 (Admin 3): Matriz CapEx / OpEx: Mantenimiento Predictivo vs. Falla Catastrófica
	 * Órdenes de Compra Auditadas con Claves de Idempotencia
	 *
	 * Cátedra: Lenguajes de Programación Visual — Facultad de Ingeniería (UNA)
	 * Svelte 5 Runes: $props, $state, $derived, $derived.by
	 */
	import { FASTAPI_BASE_URL } from '$lib/config.js';
	import { formatearGuaranies, formatearMillonesGuaranies } from '$lib/utils/moneda.js';
	import { AlertDialog } from 'bits-ui';
	import { enhance } from '$app/forms';
	import { Chart, Svg, Spline, Axis, Rule } from 'layerchart';
	import { scaleLinear } from 'd3-scale';
	import CodeViewer from '$lib/components/CodeViewer.svelte';

	let { data, form } = $props();

	// Extracción reactiva de los datos del BFF
	const capexData = $derived(data?.capexData || null);
	const activos = $derived(capexData?.activos || []);
	const presupuesto = $derived(
		capexData?.presupuesto || { presupuesto_anual_gs: 0, comprometido_gs: 0, disponible_gs: 0 }
	);
	const ordenesAprobadas = $derived(capexData?.ordenes_aprobadas || []);

	// Porcentaje de presupuesto ejecutado
	const pctComprometido = $derived.by(() => {
		if (!presupuesto.presupuesto_anual_gs) return 0;
		return (
			(presupuesto.comprometido_gs / presupuesto.presupuesto_anual_gs) *
			100
		).toFixed(1);
	});

	// Activo actualmente seleccionado para inspección en LayerChart
	let activoSeleccionadoId = $state('ACT-RED-01');

	const activoSeleccionado = $derived.by(() => {
		if (!activos.length) return null;
		const found = activos.find((a) => a.id === activoSeleccionadoId);
		return found || activos[0];
	});

	// Dominio máximo para el eje Y de la gráfica Weibull
	const maxCostoMillones = $derived.by(() => {
		if (!activoSeleccionado?.curva_weibull_12m?.length) return 800;
		const puntos = activoSeleccionado.curva_weibull_12m;
		const maxRiesgo = Math.max(...puntos.map((d) => d.costo_riesgo_esperado_millones || 0));
		const maxPrev = Math.max(...puntos.map((d) => d.costo_preventivo_millones || 0));
		return Math.ceil(Math.max(maxRiesgo, maxPrev) * 1.15);
	});

	// Estados del modal de confirmación ejecutiva Bits UI AlertDialog
	let modalAbierto = $state(false);
	let enviandoOrden = $state(false);
	let activoParaFirmar = $state(null);

	// Campos del formulario
	let directorFirmante = $state('Ing. Director de Operaciones');
	let centroCosto = $state('CC-704-MANT-PRED');
	let justificacion = $state('');
	let idempotencyKey = $state('');
	let advertenciaSimulacionDuplicada = $state(false);

	// Generación de clave de idempotencia única (UUID v4)
	function generarNuevaClave() {
		if (typeof crypto !== 'undefined' && crypto.randomUUID) {
			idempotencyKey = 'ord-capex-' + crypto.randomUUID().substring(0, 18);
		} else {
			idempotencyKey = 'ord-capex-' + Math.random().toString(36).substring(2, 10) + '-' + Date.now();
		}
		advertenciaSimulacionDuplicada = false;
	}

	// Abrir modal de confirmación ejecutiva para un activo
	function abrirModalFirma(activo) {
		activoParaFirmar = activo;
		activoSeleccionadoId = activo.id;
		justificacion = `Reemplazo preventivo prioritario de ${activo.nombre} (${activo.linea}). RUL estimado en ${activo.rul_dias_estimados} días con probabilidad de falla del ${activo.prob_falla_30d_pct}% según modelo Weibull.`;
		generarNuevaClave();
		modalAbierto = true;
	}

	// Simular reenvío duplicado para demostrar la respuesta 409
	function simularReenvioDuplicado() {
		if (ordenesAprobadas.length > 0) {
			idempotencyKey = ordenesAprobadas[0].idempotency_key;
			advertenciaSimulacionDuplicada = true;
		} else {
			idempotencyKey = 'clave-duplicada-simulada-demo-409';
			advertenciaSimulacionDuplicada = true;
		}
	}

	// Archivos para el visor pedagógico CodeViewer
	const archivosCodigo = [
		{
			nombre: '+page.server.js',
			lenguaje: 'javascript',
			codigo: `import { fail } from '@sveltejs/kit';
import { FASTAPI_BASE_URL } from '$lib/config.js';

export async function load({ fetch }) {
  try {
    const res = await fetch(\`\${FASTAPI_BASE_URL}/api/admin/capex\`);
    if (!res.ok) {
      return { fastapiOnline: false, errorConexion: 'FastAPI respondió ' + res.status };
    }
    return {
      fastapiOnline: true,
      endpointConsultado: \`\${FASTAPI_BASE_URL}/api/admin/capex\`,
      capexData: await res.json()
    };
  } catch (err) {
    return { fastapiOnline: false, errorConexion: err.message };
  }
}

export const actions = {
  aprobarOrden: async ({ request, fetch }) => {
    const formData = await request.formData();
    const activo_id = formData.get('activo_id');
    const director_firmante = formData.get('director_firmante');
    const centro_costo = formData.get('centro_costo');
    const justificacion = formData.get('justificacion');
    const idempotency_key = formData.get('idempotency_key');

    const res = await fetch(\`\${FASTAPI_BASE_URL}/api/admin/capex/aprobar-orden\`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ activo_id, director_firmante, centro_costo, justificacion, idempotency_key })
    });

    const body = await res.json().catch(() => ({}));

    // Captura estricta del 409 Conflict por Idempotencia
    if (!res.ok) {
      return fail(res.status, {
        error: body.detail || 'Error en FastAPI',
        codigoHttp: res.status,
        claveRechazada: idempotency_key
      });
    }

    return { success: true, respuesta: body };
  }
};`
		},
		{
			nombre: '+page.svelte',
			lenguaje: 'svelte',
			codigo: `<script>
  import { AlertDialog } from 'bits-ui';
  import { Chart, Svg, Spline, Axis, Rule } from 'layerchart';
  import { scaleLinear } from 'd3-scale';
  import { enhance } from '$app/forms';

  let { data, form } = $props();
  let modalAbierto = $state(false);
  let idempotencyKey = $state('');

  function generarNuevaClave() {
    idempotencyKey = 'ord-capex-' + crypto.randomUUID();
  }
<\/script>

<!-- Gráfica Weibull con LayerChart -->
<div class="layerchart-box" style="height: 320px;">
  <Chart data={activo.curva_weibull_12m} x="mes" xScale={scaleLinear()} yScale={scaleLinear()}>
    <Svg>
      <Axis placement="left" grid rule format={(d) => \`\${d} M ₲\`} />
      <Axis placement="bottom" rule format={(d) => \`Mes \${d}\`} />
      <Spline y="costo_riesgo_esperado_millones" stroke="#dc2626" strokeWidth={3} />
      <Spline y="costo_preventivo_millones" stroke="#16a34a" strokeWidth={2.5} strokeDasharray="5 4" />
    </Svg>
  </Chart>
</div>`
		},
		{
			nombre: 'FastAPI capex.py',
			lenguaje: 'python',
			codigo: `@app.post("/api/admin/capex/aprobar-orden")
async def aprobar_orden_capex(payload: AprobarOrdenRequest):
    # Verificación de Idempotencia Transaccional Financiera
    for ord_existente in capex_db["ordenes_aprobadas"]:
        if ord_existente["idempotency_key"] == payload.idempotency_key:
            raise HTTPException(
                status_code=409,
                detail=f"Rechazo por Idempotencia Financiera: La clave '{payload.idempotency_key}' ya fue ejecutada previamente. Se evitó duplicar un desembolso millonario."
            )

    # Buscar activo y verificar saldo
    # Deducir costo preventivo del presupuesto disponible
    # Registrar orden en el libro mayor inalterable
    return {"ok": True, "orden": nueva_orden, "presupuesto": capex_db["presupuesto"]}`
		}
	];
</script>

<svelte:head>
	<title>Proyecto 7: Matriz CapEx/OpEx y Órdenes Auditadas con Idempotencia — FIUNA</title>
</svelte:head>

<!-- Navegación de Migas de Pan -->
<nav class="breadcrumb has-arrow-separator mb-4" aria-label="breadcrumbs">
	<ul>
		<li>
			<a href="/" class="has-text-grey">
				<i class="fa-solid fa-house mr-1"></i> Inicio
			</a>
		</li>
		<li>
			<span class="has-text-grey">Dashboards Administrativos</span>
		</li>
		<li class="is-active">
			<a href="/admin-3-capex-mantenimiento" aria-current="page" class="has-text-weight-bold has-text-link">
				<i class="fa-solid fa-file-invoice-dollar mr-1"></i> 7. Matriz CapEx / OpEx &amp; Idempotencia
			</a>
		</li>
	</ul>
</nav>

<!-- Encabezado Principal -->
<div class="box mb-5" style="border-top: 4px solid #7c3aed; background: linear-gradient(135deg, #faf5ff 0%, #ffffff 100%);">
	<div class="columns is-vcentered">
		<div class="column is-8">
			<div class="tags has-addons mb-2">
				<span class="tag is-dark">ADMIN 03</span>
				<span class="tag is-purple has-text-white has-text-weight-bold" style="background-color: #7c3aed;">
					PROYECTO 07
				</span>
				<span class="tag is-info is-light">Tiempo Real Administrativo</span>
				<span class="tag is-danger is-light">Cientos de Millones de ₲</span>
			</div>
			<h1 class="title is-2 mb-2 has-text-dark">
				Matriz CapEx / OpEx: Mantenimiento Predictivo vs. Falla Catastrófica
			</h1>
			<p class="subtitle is-5 has-text-grey mb-3">
				Planificación de inversiones de planta, curvas Weibull de degradación y emisión de Órdenes de Compra auditadas con <strong>Claves de Idempotencia Transaccional</strong> para prevenir dobles desembolsos millonarios.
			</p>
		</div>

		<div class="column is-4 has-text-right-tablet">
			<div class="p-3 has-text-left" style="background:#ffffff; border-radius:10px; border:1px solid #e9d5ff; box-shadow: 0 4px 12px rgba(124, 58, 237, 0.08);">
				<div class="is-flex is-align-items-center is-justify-content-space-between mb-2">
					<span class="is-size-7 has-text-weight-bold has-text-grey">ESTADO SERVIDOR FASTAPI</span>
					{#if data?.fastapiOnline}
						<span class="tag is-success is-light has-text-weight-bold">
							<span class="pulse-green mr-1" style="display:inline-block; width:8px; height:8px; border-radius:50%; background:#16a34a;"></span>
							ONLINE (8007)
						</span>
					{:else}
						<span class="tag is-danger is-light has-text-weight-bold">
							<i class="fa-solid fa-circle-exclamation mr-1"></i> DESCONECTADO
						</span>
					{/if}
				</div>
				<div class="is-size-7 is-family-code mb-1 has-text-weight-semibold" style="color: #6b21a8; word-break: break-all;">
					GET /api/admin/capex
				</div>
				<p class="is-size-7 has-text-grey">
					100% de datos servidos desde el backend FastAPI (<span class="is-family-code">{FASTAPI_BASE_URL}</span>).
				</p>
			</div>
		</div>
	</div>
</div>

<!-- Alerta de Conexión si FastAPI Falla -->
{#if !data?.fastapiOnline}
	<div class="notification is-danger is-light mb-5" style="border-left: 5px solid #dc2626;">
		<div class="columns is-vcentered">
			<div class="column is-narrow">
				<span class="icon is-large has-text-danger">
					<i class="fa-solid fa-server fa-2x"></i>
				</span>
			</div>
			<div class="column">
				<h3 class="title is-5 mb-1 has-text-danger-dark">Error de Conexión con el Servidor FastAPI</h3>
				<p class="is-size-6 mb-2">
					No se pudo cargar la matriz CapEx porque el servidor en el puerto <strong>8007</strong> no responde.
				</p>
				<p class="is-size-7 is-family-code has-text-grey-dark">
					Detalle técnico: {data?.errorConexion || 'Verifica que el servicio esté corriendo con npm run backend'}
				</p>
			</div>
			<div class="column is-narrow">
				<a href="/admin-3-capex-mantenimiento" class="button is-danger is-outlined has-text-weight-semibold">
					<i class="fa-solid fa-rotate-right mr-2"></i> Reintentar Carga SSR
				</a>
			</div>
		</div>
	</div>
{/if}

<!-- Notificaciones de Feedback de la Form Action (Éxito o Rechazo 409 por Idempotencia) -->
{#if form?.success}
	<div class="notification is-success mb-5 p-4" style="border-left: 6px solid #15803d; box-shadow: 0 4px 14px rgba(22, 163, 74, 0.15);">
		<button type="button" class="delete" aria-label="Cerrar notificación" onclick={() => (form = null)}></button>
		<div class="is-flex is-align-items-start">
			<span class="icon is-large has-text-white mr-3">
				<i class="fa-solid fa-circle-check fa-2x"></i>
			</span>
			<div>
				<h4 class="title is-5 has-text-white mb-1">
					¡Orden de Compra Emitida y Presupuesto Comprometido!
				</h4>
				<p class="has-text-white-bis is-size-6 mb-2">
					{form.respuesta?.mensaje}
				</p>
				<div class="tags are-medium mb-0">
					<span class="tag is-dark is-family-code">
						ID: {form.respuesta?.orden?.orden_id}
					</span>
					<span class="tag is-white has-text-weight-bold has-text-success-dark">
						Monto: {formatearGuaranies(form.respuesta?.orden?.monto_aprobado_gs)}
					</span>
					<span class="tag is-white has-text-info-dark">
						Ahorro Proyectado: {formatearGuaranies(form.respuesta?.orden?.ahorro_riesgo_evitado_gs)}
					</span>
					<span class="tag is-dark is-family-code is-size-7">
						Hash: {form.respuesta?.orden?.hash_auditoria}
					</span>
				</div>
			</div>
		</div>
	</div>
{:else if form?.codigoHttp === 409}
	<div class="notification is-danger mb-5 p-4" style="border-left: 6px solid #b91c1c; box-shadow: 0 6px 18px rgba(220, 38, 38, 0.2);">
		<button type="button" class="delete" aria-label="Cerrar notificación" onclick={() => (form = null)}></button>
		<div class="is-flex is-align-items-start">
			<span class="icon is-large has-text-white mr-3">
				<i class="fa-solid fa-shield-halved fa-2x"></i>
			</span>
			<div>
				<h4 class="title is-5 has-text-white mb-1">
					<i class="fa-solid fa-ban mr-1"></i> Rechazo por Idempotencia Financiera (HTTP 409 Conflict)
				</h4>
				<p class="has-text-white is-size-6 mb-2 has-text-weight-semibold">
					{form.error}
				</p>
				<div class="p-3" style="background: rgba(0,0,0,0.25); border-radius: 6px;">
					<p class="is-size-7 has-text-white-bis mb-1">
						<strong>Demostración de Cátedra:</strong> La orden NO fue ejecutada por segunda vez. El backend FastAPI verificó que la clave <code class="has-text-warning">{form.claveRechazada}</code> ya figuraba en el libro mayor inmutable de desembolsos aprobados.
					</p>
					<p class="is-size-7 has-text-white-bis">
						<strong>Impacto Contable:</strong> Se evitó un débito duplicado de cientos de millones de Guaraníes provocado por un doble clic o reintento de red.
					</p>
				</div>
			</div>
		</div>
	</div>
{:else if form?.error}
	<div class="notification is-warning mb-5 p-4" style="border-left: 6px solid #d97706;">
		<button type="button" class="delete" aria-label="Cerrar" onclick={() => (form = null)}></button>
		<p class="has-text-weight-bold mb-1">
			<i class="fa-solid fa-triangle-exclamation mr-1"></i> Error al procesar la orden:
		</p>
		<p class="is-size-6">{form.error}</p>
	</div>
{/if}

<!-- ========================================================================= -->
<!-- SECCIÓN 1: CONCEPTO PEDAGÓGICO CENTRAL (CAPEX VS. FALLA & IDEMPOTENCIA)   -->
<!-- ========================================================================= -->
<div class="card mb-5" style="border: 1px solid #e2e8f0; border-radius: 10px;">
	<header class="card-header has-background-white-ter px-4 py-3">
		<p class="card-header-title is-size-6 mb-0">
			<i class="fa-solid fa-scale-balanced mr-2 has-text-link"></i>
			Concepto Central de Cátedra: Inversión Preventiva Programada vs. Catástrofe &amp; Idempotencia
		</p>
	</header>
	<div class="card-content p-4">
		<div class="columns is-multiline">
			<!-- Columna 1: CapEx Preventivo -->
			<div class="column is-12-tablet is-4-desktop">
				<div class="p-4" style="background:#f0fdf4; border-radius:8px; border-left:4px solid #16a34a; height:100%;">
					<div class="is-flex is-align-items-center mb-2">
						<span class="tag is-success is-medium mr-2">
							<i class="fa-solid fa-wrench"></i>
						</span>
						<h3 class="title is-6 mb-0 has-text-success-dark">Mantenimiento Preventivo (CapEx)</h3>
					</div>
					<p class="is-size-7 has-text-grey-dark mb-2">
						<strong>Inversión Programada:</strong> Compra planificada del activo o componente crítico (ej. Reductor Planetario: <strong>₲ 142.000.000</strong>).
					</p>
					<ul class="is-size-7 has-text-grey" style="list-style-type: disc; padding-left: 1.2rem;">
						<li>Parada técnica coordinada en fin de semana (cero lucro cesante).</li>
						<li>Flete marítimo estándar sin recargos arancelarios de urgencia.</li>
						<li>Amortización fiscal y activación como activo fijo en balance contable.</li>
					</ul>
				</div>
			</div>

			<!-- Columna 2: Falla Catastrófica -->
			<div class="column is-12-tablet is-4-desktop">
				<div class="p-4" style="background:#fef2f2; border-radius:8px; border-left:4px solid #dc2626; height:100%;">
					<div class="is-flex is-align-items-center mb-2">
						<span class="tag is-danger is-medium mr-2">
							<i class="fa-solid fa-burst"></i>
						</span>
						<h3 class="title is-6 mb-0 has-text-danger-dark">Falla Catastrófica No Programada</h3>
					</div>
					<p class="is-size-7 has-text-grey-dark mb-2">
						<strong>Gasto de Urgencia (OpEx):</strong> Colapso mecánico imprevisto en plena producción (ej. Horno Rotativo: <strong>₲ 685.000.000</strong>).
					</p>
					<ul class="is-size-7 has-text-grey" style="list-style-type: disc; padding-left: 1.2rem;">
						<li>Parada forzada de planta de 14 días (lucro cesante por botellas no entregadas).</li>
						<li>Flete aéreo internacional express de 1.8 toneladas con sobrecosto del 300%.</li>
						<li>Daños colaterales en rodamientos adyacentes y penalización de contratos.</li>
					</ul>
				</div>
			</div>

			<!-- Columna 3: Idempotencia Transaccional -->
			<div class="column is-12-tablet is-4-desktop">
				<div class="p-4" style="background:#f5f3ff; border-radius:8px; border-left:4px solid #7c3aed; height:100%;">
					<div class="is-flex is-align-items-center mb-2">
						<span class="tag is-purple has-text-white is-medium mr-2" style="background-color:#7c3aed;">
							<i class="fa-solid fa-fingerprint"></i>
						</span>
						<h3 class="title is-6 mb-0 has-text-dark">Idempotencia Financiera (<code class="is-size-7">idempotency_key</code>)</h3>
					</div>
					<p class="is-size-7 has-text-grey-dark mb-2">
						<strong>Seguridad contra Doble Cobro:</strong> Una transacción bancaria o de ERP de cientos de millones de ₲ no admite fallos de red.
					</p>
					<ul class="is-size-7 has-text-grey" style="list-style-type: disc; padding-left: 1.2rem;">
						<li>El cliente SvelteKit genera un UUID v4 antes de firmar.</li>
						<li>FastAPI valida que la clave no haya sido ejecutada previamente.</li>
						<li>Si el usuario hace doble clic o la red reintenta, el backend responde <strong>HTTP 409 Conflict</strong>.</li>
					</ul>
				</div>
			</div>
		</div>
	</div>
</div>

<!-- ========================================================================= -->
<!-- SECCIÓN 2: RESUMEN PRESUPUESTARIO ANUAL EN GUARANÍES (₲)                  -->
<!-- ========================================================================= -->
<div class="mb-5">
	<div class="level mb-2">
		<div class="level-left">
			<div>
				<h2 class="title is-4 mb-0">
					<i class="fa-solid fa-vault mr-2 has-text-warning-dark"></i>
					Presupuesto Anual CapEx de Planta (Ejercicio 2026)
				</h2>
				<p class="is-size-7 has-text-grey">
					Control de compromisos financieros en Guaraníes sin céntimos (Intl.NumberFormat es-PY)
				</p>
			</div>
		</div>
		<div class="level-right">
			<span class="tag is-dark is-medium is-family-code">
				Ejecución: {pctComprometido}%
			</span>
		</div>
	</div>

	<div class="columns is-multiline mb-2">
		<!-- KPI 1: Presupuesto Anual CapEx -->
		<div class="column is-12-tablet is-4-desktop">
			<div class="card p-4" style="border-radius:10px; border-left: 5px solid #2563eb; background:#ffffff;">
				<div class="is-flex is-justify-content-space-between is-align-items-center mb-1">
					<span class="is-size-7 has-text-weight-bold has-text-grey">PRESUPUESTO ANUAL CAPEX</span>
					<span class="tag is-info is-light">FONDO FIJO</span>
				</div>
				<div class="title is-3 mb-1 has-text-link">
					{formatearGuaranies(presupuesto.presupuesto_anual_gs)}
				</div>
				<p class="is-size-7 has-text-grey">
					Asignación corporativa total para renovación de activos críticos y mitigación de fallas.
				</p>
			</div>
		</div>

		<!-- KPI 2: Monto Comprometido en Órdenes -->
		<div class="column is-12-tablet is-4-desktop">
			<div class="card p-4" style="border-radius:10px; border-left: 5px solid #f59e0b; background:#ffffff;">
				<div class="is-flex is-justify-content-space-between is-align-items-center mb-1">
					<span class="is-size-7 has-text-weight-bold has-text-grey">MONTO COMPROMETIDO EN ÓRDENES</span>
					<span class="tag is-warning is-light">EJECUTADO</span>
				</div>
				<div class="title is-3 mb-1 has-text-warning-dark">
					{formatearGuaranies(presupuesto.comprometido_gs)}
				</div>
				<p class="is-size-7 has-text-grey">
					Total desembolsado en órdenes de compra firmadas por la Dirección de Operaciones.
				</p>
			</div>
		</div>

		<!-- KPI 3: Saldo Presupuestario Disponible -->
		<div class="column is-12-tablet is-4-desktop">
			<div class="card p-4" style="border-radius:10px; border-left: 5px solid #16a34a; background:#ffffff;">
				<div class="is-flex is-justify-content-space-between is-align-items-center mb-1">
					<span class="is-size-7 has-text-weight-bold has-text-grey">SALDO PRESUPUESTARIO DISPONIBLE</span>
					<span class="tag is-success is-light">DISPONIBLE</span>
				</div>
				<div class="title is-3 mb-1 has-text-success-dark">
					{formatearGuaranies(presupuesto.disponible_gs)}
				</div>
				<p class="is-size-7 has-text-grey">
					Margen remanente para contingencias y adquisición de repuestos preventivos pendientes.
				</p>
			</div>
		</div>
	</div>

	<!-- Barra de Progreso de Ejecución Presupuestaria -->
	<div class="p-3" style="background:#f8fafc; border-radius:8px; border:1px solid #e2e8f0;">
		<div class="is-flex is-justify-content-space-between is-size-7 mb-1">
			<span class="has-text-weight-semibold has-text-grey">Consumo Presupuestario Global:</span>
			<span class="has-text-weight-bold">{pctComprometido}% utilizado</span>
		</div>
		<progress class="progress is-link mb-0" value={pctComprometido} max="100"></progress>
	</div>
</div>

<!-- ========================================================================= -->
<!-- SECCIÓN 3: MATRIZ DE ACTIVOS CRÍTICOS & GRÁFICA WEIBULL EN LAYERCHART    -->
<!-- ========================================================================= -->
<div class="card mb-5" style="border: 1px solid #cbd5e1; border-radius: 10px;">
	<header class="card-header has-background-white-ter px-4 py-3 is-flex is-justify-content-space-between is-align-items-center">
		<div>
			<p class="card-header-title is-size-5 mb-0 p-0">
				<i class="fa-solid fa-chart-line mr-2 has-text-danger"></i>
				Matriz de Activos Críticos &amp; Curva de Degradación Weibull (12 Meses)
			</p>
			<p class="is-size-7 has-text-grey">
				Selecciona un activo para comparar la línea plana de CapEx frente al crecimiento exponencial de falla
			</p>
		</div>
		<span class="tag is-purple has-text-white is-medium" style="background-color: #7c3aed;">
			LayerChart SVG
		</span>
	</header>

	<div class="card-content p-4">
		<!-- Selector de los 4 Activos Críticos -->
		<div class="columns is-multiline mb-4">
			{#each activos as act (act.id)}
				<div class="column is-12-tablet is-3-desktop">
					<button
						type="button"
						class="card p-3 has-text-left is-fullwidth"
						style="cursor:pointer; border-radius:8px; transition: all 0.2s ease; border: 2px solid {activoSeleccionadoId === act.id ? '#7c3aed' : '#e2e8f0'}; background: {activoSeleccionadoId === act.id ? '#fbf8ff' : '#ffffff'};"
						onclick={() => (activoSeleccionadoId = act.id)}
					>
						<div class="is-flex is-justify-content-space-between is-align-items-center mb-1">
							<span class="tag is-dark is-family-code is-small">{act.id}</span>
							{#if act.estado_orden === 'ORDEN_EMITIDA'}
								<span class="tag is-success is-light is-small has-text-weight-bold">
									<i class="fa-solid fa-check mr-1"></i> APROBADO
								</span>
							{:else}
								<span class="tag is-danger is-light is-small has-text-weight-bold">
									P(falla): {act.prob_falla_30d_pct}%
								</span>
							{/if}
						</div>
						<h4 class="title is-6 mb-1 has-text-dark" style="line-height: 1.2;">
							{act.nombre}
						</h4>
						<p class="is-size-7 has-text-grey mb-2">
							<i class="fa-solid fa-location-dot mr-1"></i> {act.linea}
						</p>
						<div class="is-flex is-justify-content-space-between is-size-7">
							<span class="has-text-grey">RUL Estimado:</span>
							<span class="has-text-weight-bold {act.rul_dias_estimados < 30 ? 'has-text-danger' : 'has-text-link'}">
								{act.rul_dias_estimados} días
							</span>
						</div>
						<div class="is-flex is-justify-content-space-between is-size-7 mt-1">
							<span class="has-text-grey">CapEx:</span>
							<span class="has-text-weight-bold has-text-success-dark">
								{formatearMillonesGuaranies(act.costo_preventivo_capex_gs)}
							</span>
						</div>
					</button>
				</div>
			{/each}
		</div>

		<!-- Detalle del Activo Seleccionado y Gráfica LayerChart -->
		{#if activoSeleccionado}
			<div class="box p-4 mb-4" style="background:#fafafa; border:1px solid #e2e8f0; border-radius:8px;">
				<div class="columns is-vcentered mb-3">
					<div class="column is-7">
						<div class="tags has-addons mb-1">
							<span class="tag is-dark is-family-code">{activoSeleccionado.id}</span>
							<span class="tag is-link">{activoSeleccionado.linea}</span>
							{#if activoSeleccionado.estado_orden === 'ORDEN_EMITIDA'}
								<span class="tag is-success has-text-weight-bold">
									<i class="fa-solid fa-file-circle-check mr-1"></i> ORDEN EMITIDA
								</span>
							{:else}
								<span class="tag is-warning has-text-weight-bold">
									<i class="fa-solid fa-clock mr-1"></i> PENDIENTE DE DECISIÓN
								</span>
							{/if}
						</div>
						<h3 class="title is-4 mb-1 has-text-dark">
							{activoSeleccionado.nombre}
						</h3>
						<p class="is-size-7 has-text-grey">
							Vida Útil Remanente: <strong>{activoSeleccionado.rul_dias_estimados} días</strong> | Riesgo Ponderado a 30 días: <strong>{formatearGuaranies(activoSeleccionado.riesgo_ponderado_gs)}</strong>
						</p>
					</div>

					<div class="column is-5 has-text-right-tablet">
						{#if activoSeleccionado.estado_orden === 'ORDEN_EMITIDA'}
							<button class="button is-success is-light" disabled>
								<i class="fa-solid fa-check-double mr-2"></i> Orden de Compra ya Emitida
							</button>
						{:else}
							<button
								type="button"
								class="button is-purple has-text-white has-text-weight-bold"
								style="background-color: #7c3aed; box-shadow: 0 4px 14px rgba(124, 58, 237, 0.35);"
								onclick={() => abrirModalFirma(activoSeleccionado)}
							>
								<i class="fa-solid fa-file-signature mr-2"></i>
								Firmar Orden CapEx ({formatearMillonesGuaranies(activoSeleccionado.costo_preventivo_capex_gs)})
							</button>
						{/if}
					</div>
				</div>

				<!-- Métricas Económicas del Activo -->
				<div class="columns is-multiline mb-3">
					<div class="column is-3">
						<div class="p-3 has-background-white" style="border-radius:6px; border:1px solid #e2e8f0;">
							<p class="is-size-7 has-text-grey">CapEx Preventivo:</p>
							<p class="title is-5 mb-0 has-text-success-dark">
								{formatearGuaranies(activoSeleccionado.costo_preventivo_capex_gs)}
							</p>
						</div>
					</div>
					<div class="column is-3">
						<div class="p-3 has-background-white" style="border-radius:6px; border:1px solid #e2e8f0;">
							<p class="is-size-7 has-text-grey">Costo Falla Catastrófica:</p>
							<p class="title is-5 mb-0 has-text-danger">
								{formatearGuaranies(activoSeleccionado.costo_falla_catastrofica_gs)}
							</p>
						</div>
					</div>
					<div class="column is-3">
						<div class="p-3 has-background-white" style="border-radius:6px; border:1px solid #e2e8f0;">
							<p class="is-size-7 has-text-grey">Ahorro por Riesgo Evitado:</p>
							<p class="title is-5 mb-0 has-text-link">
								{formatearGuaranies(activoSeleccionado.costo_falla_catastrofica_gs - activoSeleccionado.costo_preventivo_capex_gs)}
							</p>
						</div>
					</div>
					<div class="column is-3">
						<div class="p-3 has-background-white" style="border-radius:6px; border:1px solid #e2e8f0;">
							<p class="is-size-7 has-text-grey">Prob. Falla Acumulada:</p>
							<p class="title is-5 mb-0 has-text-warning-dark">
								{activoSeleccionado.prob_falla_30d_pct}%
							</p>
						</div>
					</div>
				</div>

				<!-- Leyenda Visual de la Gráfica -->
				<div class="is-flex is-align-items-center mb-2 is-justify-content-space-between" style="flex-wrap: wrap; gap: 0.5rem;">
					<div class="is-flex is-align-items-center" style="gap: 1.25rem;">
						<span class="is-size-7 is-flex is-align-items-center">
							<span style="display:inline-block; width:16px; height:3px; background:#16a34a; margin-right:6px; border-bottom: 2px dashed #16a34a;"></span>
							<strong>Línea Verde:</strong> Costo Preventivo Programado ({formatearMillonesGuaranies(activoSeleccionado.costo_preventivo_capex_gs)} fijo)
						</span>
						<span class="is-size-7 is-flex is-align-items-center">
							<span style="display:inline-block; width:16px; height:3px; background:#dc2626; margin-right:6px;"></span>
							<strong>Curva Roja:</strong> Riesgo Acumulado de Falla Catastrófica (Weibull exponencial)
						</span>
					</div>
					<span class="tag is-light is-size-7">
						Eje X: Meses 1 a 12 | Eje Y: Millones de ₲
					</span>
				</div>

				<!-- Gráfica LayerChart Oficial -->
				<div class="layerchart-box" style="height: 330px;">
					{#if activoSeleccionado.curva_weibull_12m && activoSeleccionado.curva_weibull_12m.length > 0}
						<Chart
							data={activoSeleccionado.curva_weibull_12m}
							x="mes"
							y="costo_riesgo_esperado_millones"
							xScale={scaleLinear()}
							yScale={scaleLinear()}
							yDomain={[0, maxCostoMillones]}
							padding={{ top: 20, right: 30, bottom: 35, left: 65 }}
						>
							<Svg>
								<Axis placement="left" grid rule format={(d) => `${d} M ₲`} />
								<Axis placement="bottom" rule format={(d) => `Mes ${d}`} />
								<!-- Curva 1: Riesgo acumulado exponencial en rojo -->
								<Spline
									y="costo_riesgo_esperado_millones"
									stroke="#dc2626"
									strokeWidth={3}
								/>
								<!-- Curva 2: Costo preventivo CapEx plano en verde -->
								<Spline
									y="costo_preventivo_millones"
									stroke="#16a34a"
									strokeWidth={2.5}
									strokeDasharray="5 4"
								/>
								<!-- Regla horizontal de cota presupuestaria preventiva -->
								<Rule
									y={activoSeleccionado.curva_weibull_12m[0]?.costo_preventivo_millones}
									style="stroke: #16a34a; stroke-width: 1.5px; stroke-dasharray: 4,4;"
								/>
							</Svg>
						</Chart>
					{:else}
						<div class="is-flex is-align-items-center is-justify-content-center" style="height: 100%;">
							<p class="has-text-grey is-size-6">Sin datos de curva Weibull disponibles para este activo.</p>
						</div>
					{/if}
				</div>

				<div class="p-3 mt-3 is-size-7" style="background:#f1f5f9; border-radius:6px; border:1px solid #cbd5e1;">
					<i class="fa-solid fa-circle-info mr-1 has-text-info"></i>
					<strong>Interpretación Mecatrónica-Económica:</strong> A partir del punto en que la curva roja de <em>Riesgo Esperado</em> cruza la línea verde punteada de <em>Costo Preventivo</em>, postergar la sustitución del componente resulta financieramente irracional. Cada día adicional de operación sin reemplazo expone a la planta a un costo medio 4.8 veces superior debido al lucro cesante acumulativo.
				</div>
			</div>
		{/if}
	</div>
</div>

<!-- ========================================================================= -->
<!-- SECCIÓN 4: LIBRO MAYOR DE ÓRDENES DE COMPRA AUDITADAS CON IDEMPOTENCIA    -->
<!-- ========================================================================= -->
<div class="card mb-5" style="border: 1px solid #cbd5e1; border-radius: 10px;">
	<header class="card-header has-background-white-ter px-4 py-3 is-flex is-justify-content-space-between is-align-items-center">
		<div>
			<p class="card-header-title is-size-5 mb-0 p-0">
				<i class="fa-solid fa-book-bookmark mr-2 has-text-link"></i>
				Libro Mayor de Órdenes de Compra Auditadas (FastAPI)
			</p>
			<p class="is-size-7 has-text-grey">
				Registro inmutable de desembolsos aprobados, firmantes y claves de idempotencia registradas
			</p>
		</div>
		<span class="tag is-dark is-medium">
			{ordenesAprobadas.length} {ordenesAprobadas.length === 1 ? 'orden emitida' : 'órdenes emitidas'}
		</span>
	</header>

	<div class="card-content p-0">
		<div class="table-container mb-0">
			<table class="table is-fullwidth is-striped is-hoverable mb-0 is-size-7">
				<thead>
					<tr style="background:#f8fafc;">
						<th>CÓDIGO / FECHA</th>
						<th>ACTIVO CRÍTICO</th>
						<th>MONTO CAPEX (₲)</th>
						<th>AHORRO RIESGO (₲)</th>
						<th>DIRECTOR / CENTRO COSTO</th>
						<th>IDEMPOTENCY KEY</th>
						<th>HASH AUDITORÍA</th>
					</tr>
				</thead>
				<tbody>
					{#if ordenesAprobadas.length === 0}
						<tr>
							<td colspan="7" class="has-text-centered py-5 has-text-grey">
								<i class="fa-solid fa-inbox fa-2x mb-2" style="display:block; opacity:0.4;"></i>
								Aún no se han emitido órdenes de compra en esta sesión. Selecciona un activo arriba y pulsa <strong>"Firmar Orden CapEx"</strong> para iniciar la primera transacción auditada.
							</td>
						</tr>
					{:else}
						{#each ordenesAprobadas as ord (ord.orden_id)}
							<tr>
								<td>
									<span class="tag is-dark is-family-code has-text-weight-bold mb-1">
										{ord.orden_id}
									</span>
									<br />
									<span class="has-text-grey is-size-7">{ord.timestamp}</span>
								</td>
								<td>
									<strong>{ord.nombre_activo}</strong>
									<br />
									<span class="tag is-light is-family-code is-size-7">{ord.activo_id}</span>
								</td>
								<td class="has-text-weight-bold has-text-success-dark is-size-6">
									{formatearGuaranies(ord.monto_aprobado_gs)}
								</td>
								<td class="has-text-weight-semibold has-text-info">
									{formatearGuaranies(ord.ahorro_riesgo_evitado_gs)}
								</td>
								<td>
									<strong>{ord.director_firmante}</strong>
									<br />
									<span class="tag is-light">{ord.centro_costo}</span>
								</td>
								<td>
									<code class="is-size-7" style="background:#f1f5f9; padding:2px 6px; border-radius:4px; color:#6b21a8;">
										{ord.idempotency_key}
									</code>
								</td>
								<td>
									<span class="tag is-info is-light is-family-code is-size-7">
										{ord.hash_auditoria}
									</span>
								</td>
							</tr>
						{/each}
					{/if}
				</tbody>
			</table>
		</div>
	</div>
</div>

<!-- ========================================================================= -->
<!-- MODAL DE AUTORIZACIÓN EJECUTIVA CON BITS UI (AlertDialog)                 -->
<!-- ========================================================================= -->
<AlertDialog.Root bind:open={modalAbierto}>
	<AlertDialog.Portal>
		<AlertDialog.Overlay class="scada-dialog-overlay" />
		<AlertDialog.Content class="scada-dialog-content">
			{#if activoParaFirmar}
				<header class="p-4 is-flex is-align-items-center" style="background:#faf5ff; border-bottom:1px solid #e9d5ff;">
					<span class="tag is-purple has-text-white is-large mr-3" style="background-color:#7c3aed;">
						<i class="fa-solid fa-signature"></i>
					</span>
					<div>
						<AlertDialog.Title class="title is-4 mb-0 has-text-dark">
							Autorización Ejecutiva de Desembolso CapEx
						</AlertDialog.Title>
						<p class="is-size-7 has-text-grey">
							Doble confirmación con clave única de idempotencia contra doble cobro millonario
						</p>
					</div>
				</header>

				<div class="p-5">
					<AlertDialog.Description class="is-size-6 mb-3">
						¿Confirma la emisión irrevocable de la Orden de Compra para sustitución preventiva del activo
						<strong class="has-text-purple" style="color:#7c3aed;">{activoParaFirmar.nombre}</strong>?
					</AlertDialog.Description>

					<!-- Resumen Contable del Activo en el Modal -->
					<div class="p-3 mb-4" style="background:#f8fafc; border-radius:8px; border:1px solid #e2e8f0;">
						<div class="columns is-mobile is-multiline">
							<div class="column is-6">
								<span class="is-size-7 has-text-grey">Activo / Línea:</span>
								<p class="is-size-7 has-text-weight-bold">{activoParaFirmar.id} ({activoParaFirmar.linea})</p>
							</div>
							<div class="column is-6">
								<span class="is-size-7 has-text-grey">Monto CapEx a Desembolsar:</span>
								<p class="is-size-6 has-text-weight-bold has-text-success-dark">
									{formatearGuaranies(activoParaFirmar.costo_preventivo_capex_gs)}
								</p>
							</div>
							<div class="column is-6">
								<span class="is-size-7 has-text-grey">Riesgo Falla Evitado:</span>
								<p class="is-size-7 has-text-weight-bold has-text-info">
									{formatearGuaranies(activoParaFirmar.costo_falla_catastrofica_gs)}
								</p>
							</div>
							<div class="column is-6">
								<span class="is-size-7 has-text-grey">Saldo Disponible tras Firma:</span>
								<p class="is-size-7 has-text-weight-bold has-text-link">
									{formatearGuaranies(presupuesto.disponible_gs - activoParaFirmar.costo_preventivo_capex_gs)}
								</p>
							</div>
						</div>
					</div>

					<!-- Formulario de Aprobación con use:enhance -->
					<form
						method="POST"
						action="?/aprobarOrden"
						use:enhance={() => {
							enviandoOrden = true;
							return async ({ update }) => {
								await update();
								enviandoOrden = false;
								if (form?.success) {
									modalAbierto = false;
								}
							};
						}}
					>
						<input type="hidden" name="activo_id" value={activoParaFirmar.id} />

						<div class="field mb-3">
							<label class="label is-small" for="director_firmante">Director Firmante / Responsable:</label>
							<div class="control has-icons-left">
								<input
									id="director_firmante"
									class="input is-small"
									type="text"
									name="director_firmante"
									bind:value={directorFirmante}
									required
								/>
								<span class="icon is-small is-left">
									<i class="fa-solid fa-user-tie"></i>
								</span>
							</div>
						</div>

						<div class="field mb-3">
							<label class="label is-small" for="centro_costo">Centro de Costo Imputable:</label>
							<div class="control has-icons-left">
								<input
									id="centro_costo"
									class="input is-small is-family-code"
									type="text"
									name="centro_costo"
									bind:value={centroCosto}
									required
								/>
								<span class="icon is-small is-left">
									<i class="fa-solid fa-building-columns"></i>
								</span>
							</div>
						</div>

						<div class="field mb-3">
							<label class="label is-small" for="justificacion">Justificación Técnica del Dictamen:</label>
							<div class="control">
								<textarea
									id="justificacion"
									class="textarea is-small"
									name="justificacion"
									rows="2"
									bind:value={justificacion}
									required
								></textarea>
							</div>
						</div>

						<!-- Clave de Idempotencia y Prueba Didáctica 409 -->
						<div class="field mb-4 p-3" style="background:#faf5ff; border:1px solid #d8b4fe; border-radius:6px;">
							<div class="is-flex is-justify-content-space-between is-align-items-center mb-1">
								<label class="label is-small mb-0 has-text-dark" for="idempotency_key">
									<i class="fa-solid fa-key mr-1 has-text-purple" style="color:#7c3aed;"></i>
									Clave de Idempotencia (<code class="is-size-7">idempotency_key</code>):
								</label>
								<button
									type="button"
									class="button is-white is-small p-1"
									title="Generar nueva clave única UUID v4"
									onclick={generarNuevaClave}
								>
									<i class="fa-solid fa-arrows-rotate mr-1"></i> Nueva clave
								</button>
							</div>
							<div class="control">
								<input
									id="idempotency_key"
									class="input is-small is-family-code"
									type="text"
									name="idempotency_key"
									bind:value={idempotencyKey}
									required
								/>
							</div>

							{#if advertenciaSimulacionDuplicada}
								<div class="mt-2 p-2 is-size-7 has-text-danger-dark" style="background:#fef2f2; border-radius:4px; border:1px solid #fecaca;">
									<i class="fa-solid fa-triangle-exclamation mr-1"></i>
									<strong>Modo Simulación 409 Activado:</strong> Se cargó una clave que ya fue ejecutada. Al pulsar el botón de confirmación, FastAPI rechazará la petición con <strong>HTTP 409 Conflict</strong>.
								</div>
							{/if}

							<!-- Botón Didáctico de Prueba de Idempotencia 409 -->
							<div class="mt-2">
								<button
									type="button"
									class="button is-warning is-light is-small is-fullwidth has-text-weight-bold"
									onclick={simularReenvioDuplicado}
								>
									<i class="fa-solid fa-copy mr-1"></i>
									Simular Reenvío Duplicado (Probar Idempotencia 409)
								</button>
							</div>
						</div>

						<footer class="is-flex is-justify-content-flex-end" style="gap: 0.75rem;">
							<AlertDialog.Cancel class="button is-light has-text-weight-semibold">
								Cancelar Maniobra
							</AlertDialog.Cancel>
							<button
								type="submit"
								class="button is-purple has-text-white has-text-weight-bold {enviandoOrden ? 'is-loading' : ''}"
								style="background-color: #7c3aed;"
							>
								<i class="fa-solid fa-stamp mr-2"></i>
								Firmar y Emitir Orden de Desembolso
							</button>
						</footer>
					</form>
				</div>
			{/if}
		</AlertDialog.Content>
	</AlertDialog.Portal>
</AlertDialog.Root>

<!-- ========================================================================= -->
<!-- SECCIÓN 5: VISOR DE CÓDIGO FUENTE DIDÁCTICO (<CodeViewer>)                -->
<!-- ========================================================================= -->
<CodeViewer
	titulo="Implementación Técnica: SvelteKit BFF, LayerChart Weibull e Idempotencia FastAPI"
	archivos={archivosCodigo}
/>

<style>
	:global(.scada-dialog-overlay) {
		position: fixed;
		inset: 0;
		background-color: rgba(15, 23, 42, 0.75);
		backdrop-filter: blur(4px);
		z-index: 9998;
		animation: capexFadeIn 0.15s ease-out;
	}

	:global(.scada-dialog-content) {
		position: fixed;
		top: 50%;
		left: 50%;
		transform: translate(-50%, -50%);
		width: 92%;
		max-width: 640px;
		max-height: 90vh;
		overflow-y: auto;
		background: #ffffff;
		border-radius: 12px;
		box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.45);
		z-index: 9999;
		outline: none;
		border: 1px solid #cbd5e1;
		animation: capexScaleUp 0.18s cubic-bezier(0.16, 1, 0.3, 1);
	}

	@keyframes capexFadeIn {
		from { opacity: 0; }
		to { opacity: 1; }
	}

	@keyframes capexScaleUp {
		from {
			opacity: 0;
			transform: translate(-50%, -47%) scale(0.96);
		}
		to {
			opacity: 1;
			transform: translate(-50%, -50%) scale(1);
		}
	}
</style>
