<script>
	/**
	 * Componente de visualización industrial de un nodo transductor.
	 * Svelte 5 Runes: $props, $derived, {#snippet}, {@render}
	 *
	 * Cátedra: Lenguajes de Programación Visual — FIUNA
	 */
	let {
		sensor,
		estadoPlanta = 'EN_MARCHA',
		alertaSnippet,
		footerSnippet
	} = $props();

	// Cálculo del porcentaje del rango máximo con límite seguro [0, 100]
	const porcentaje = $derived(
		sensor && sensor.rango_max > 0
			? Math.min(100, Math.max(0, ((sensor.valor_actual ?? 0) / sensor.rango_max) * 100))
			: 0
	);

	// Detección estricta de condición anómala (sobrepaso de rango_max)
	const anomalia = $derived(
		sensor ? Number(sensor.valor_actual ?? 0) > Number(sensor.rango_max ?? 0) : false
	);

	// Nivel de severidad para estilos CSS Bulma
	const severidad = $derived(
		anomalia ? 'danger' : porcentaje > 80 ? 'warning' : 'success'
	);

	// Formateo mecatrónico de offset de calibración activo (+/-X.XX)
	const offsetFormateado = $derived(
		sensor && typeof sensor.offset === 'number'
			? (sensor.offset >= 0 ? `+${sensor.offset.toFixed(2)}` : sensor.offset.toFixed(2))
			: '+0.00'
	);

	// Valor numérico formateado
	const valorFormateado = $derived(
		sensor && typeof sensor.valor_actual === 'number'
			? sensor.valor_actual.toFixed(1)
			: '--'
	);
</script>

<div
	class="card sensor-card {anomalia ? 'anomalia-activa' : ''} {estadoPlanta === 'PARO_EMERGENCIA' ? 'planta-en-paro' : ''}"
	style="height: 100%; display: flex; flex-direction: column;"
>
	<!-- Cabecera de la Tarjeta con Tag de Red y Modelo -->
	<header class="card-header p-3 is-justify-content-space-between is-align-items-center">
		<div>
			<span class="tag is-dark is-family-code has-text-weight-bold mr-2">
				{sensor?.id || 'ID-XXX'}
			</span>
			<span class="has-text-weight-bold is-size-6">{sensor?.nombre || 'Transductor'}</span>
		</div>
		<div class="tags has-addons mb-0">
			<span class="tag is-info is-light is-size-7" title="Nodo Microcontrolador">
				<i class="fa-solid fa-microchip mr-1"></i>
				{sensor?.nodo || 'ESP32'}
			</span>
			<span class="tag is-primary is-light is-size-7" title="Modelo de Sensor">
				{sensor?.modelo || 'Genérico'}
			</span>
		</div>
	</header>

	<!-- Cuerpo: Lectura Principal y Metrología -->
	<div class="card-content p-4" style="flex: 1 1 auto;">
		{#if estadoPlanta === 'PARO_EMERGENCIA'}
			<div class="notification is-danger is-light p-2 mb-2 is-size-7 has-text-centered has-text-weight-bold">
				<i class="fa-solid fa-ban mr-1"></i> PLANTA EN PARO: LECTURA CONGELADA
			</div>
		{/if}

		<div class="level is-mobile mb-2">
			<div class="level-left">
				<div class="lectura-principal">
					<span class="valor is-family-code {anomalia ? 'has-text-danger has-text-weight-bold' : 'has-text-dark'}">
						{valorFormateado}
					</span>
					<span class="unidad is-size-5 has-text-grey ml-1">{sensor?.unidad || ''}</span>
				</div>
			</div>
			<div class="level-right">
				{#if anomalia}
					<span class="tag is-danger has-text-weight-bold pulse-badge">
						<i class="fa-solid fa-triangle-exclamation mr-1"></i> ANOMALÍA
					</span>
				{:else if porcentaje > 80}
					<span class="tag is-warning has-text-weight-bold">
						<i class="fa-solid fa-triangle-exclamation mr-1"></i> ALTO
					</span>
				{:else}
					<span class="tag is-success is-light has-text-weight-semibold">
						<i class="fa-solid fa-circle-check mr-1"></i> NORMAL
					</span>
				{/if}
			</div>
		</div>

		<!-- Barra de Nivel Metrológica -->
		<div class="mb-2">
			<progress
				class="progress is-small is-{severidad} mb-1"
				value={porcentaje}
				max="100"
			>
				{porcentaje.toFixed(0)}%
			</progress>
			<div class="is-flex is-justify-content-space-between is-size-7 has-text-grey">
				<span>0 {sensor?.unidad || ''}</span>
				<span class="has-text-weight-semibold">
					Límite: {sensor?.rango_max ?? 100} {sensor?.unidad || ''}
				</span>
			</div>
		</div>

		<!-- Metadatos de Calibración Activa -->
		<div class="tags has-addons mb-2 is-size-7">
			<span class="tag is-light">Offset EEPROM:</span>
			<span class="tag is-white is-family-code has-text-weight-bold" style="border: 1px solid #e2e8f0;">
				{offsetFormateado} {sensor?.unidad || ''}
			</span>
			<span class="tag is-light ml-auto">
				<i class="fa-solid fa-wave-square mr-1"></i> {sensor?.frecuencia_muestreo_hz || 10} Hz
			</span>
		</div>

		<!-- Renderizado Condicional del Snippet de Alerta (Svelte 5 Runes) -->
		{#if anomalia && alertaSnippet}
			<div class="mt-2">
				{@render alertaSnippet(sensor)}
			</div>
		{/if}

		<!-- Renderizado Condicional del Snippet de Footer Opcional -->
		{#if footerSnippet}
			<div class="mt-2">
				{@render footerSnippet(sensor)}
			</div>
		{/if}
	</div>

	<!-- Pie de Tarjeta con Enlace hacia la Vista Dinámica de Calibración -->
	<footer class="card-footer" style="background-color: #f8fafc; border-top: 1px solid #e2e8f0;">
		<a
			href="/proyecto-4-scada/sensores/{sensor?.id || 'TI-101'}"
			class="card-footer-item button is-white has-text-link has-text-weight-bold is-radiusless"
			style="border: none;"
		>
			<i class="fa-solid fa-sliders mr-2"></i> Inspeccionar y Calibrar Nodo
		</a>
	</footer>
</div>

<style>
	.sensor-card {
		border-radius: 10px;
		border: 1px solid #cbd5e1;
		transition: transform 0.15s ease, box-shadow 0.15s ease;
		background: #ffffff;
	}

	.sensor-card:hover {
		box-shadow: 0 8px 20px -4px rgba(15, 23, 42, 0.15);
	}

	.anomalia-activa {
		border: 2px solid #ef4444 !important;
		background-color: #fef2f2 !important;
		animation: pulse-border 1.5s infinite;
	}

	.planta-en-paro {
		border-left: 5px solid #dc2626 !important;
		filter: grayscale(0.2);
	}

	.lectura-principal .valor {
		font-size: 2.1rem;
		line-height: 1;
		letter-spacing: -0.03em;
	}

	@keyframes pulse-border {
		0%, 100% {
			box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4);
		}
		50% {
			box-shadow: 0 0 0 6px rgba(239, 68, 68, 0.15);
		}
	}

	@keyframes pulse-badge-anim {
		0%, 100% { opacity: 1; }
		50% { opacity: 0.75; }
	}

	.pulse-badge {
		animation: pulse-badge-anim 1s infinite;
	}
</style>
