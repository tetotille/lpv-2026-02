<script>
	/**
	 * Componente de Paro de Emergencia Administrativo con Bits UI (AlertDialog).
	 * Explica con rigor mecatrónico por qué la web NO sustituye a un Relé Cat. 4 / PLe.
	 *
	 * Svelte 5 Runes: $props, $state, $derived
	 * Cátedra: Lenguajes de Programación Visual — FIUNA
	 */
	import { AlertDialog } from 'bits-ui';
	import { enhance } from '$app/forms';

	let {
		estadoPlanta = 'EN_MARCHA',
		latenciaRttMs = null,
		ultimoEvento = null
	} = $props();

	let modalAbierto = $state(false);
	let procesando = $state(false);
	let motivo = $state('Detección preventiva de sobrepresión en Caldera / Inspección SCADA');
	let operador = $state('Ing. Operador SCADA - Turno A');

	const estaEnParo = $derived(estadoPlanta === 'PARO_EMERGENCIA');
</script>

<!-- Disparador Visual Industrial Destacado -->
<div class="emergency-trigger-box">
	{#if estaEnParo}
		<div class="notification is-danger mb-3 p-4 has-text-centered has-text-white paro-pulse-banner">
			<h3 class="title is-4 has-text-white mb-1">
				<i class="fa-solid fa-triangle-exclamation mr-2"></i> ¡PLANTA EN PARO DE EMERGENCIA!
			</h3>
			<p class="is-size-7 mb-3">
				La línea de producción se encuentra detenida administrativamente. Todos los lazos de control
				están suspendidos.
			</p>

			<AlertDialog.Root bind:open={modalAbierto}>
				<AlertDialog.Trigger class="button is-warning is-medium has-text-weight-bold is-rounded">
					<i class="fa-solid fa-rotate-left mr-2"></i> Abrir Consola de Rearme y Restauración
				</AlertDialog.Trigger>

				<AlertDialog.Portal>
					<AlertDialog.Overlay class="scada-dialog-overlay" />
					<AlertDialog.Content class="scada-dialog-content">
						<header class="p-4 is-flex is-align-items-center" style="background:#fffbeb; border-bottom:1px solid #fde68a;">
							<span class="tag is-warning is-large mr-3">
								<i class="fa-solid fa-rotate-left"></i>
							</span>
							<div>
								<AlertDialog.Title class="title is-4 mb-0 has-text-dark">
									Procedimiento de Rearme de Planta
								</AlertDialog.Title>
								<p class="is-size-7 has-text-grey">
									Protocolo SCADA de reinicio administrativo de transductores y lazos PID
								</p>
							</div>
						</header>

						<div class="p-4">
							<AlertDialog.Description class="is-size-6 mb-4">
								¿Confirma que la zona de máquinas ha sido despejada y que las condiciones
								termodinámicas se encuentran dentro de las cotas seguras para reanudar la marcha?
							</AlertDialog.Description>

							<!-- Formulario de Rearme con use:enhance -->
							<form
								method="POST"
								action="?/restaurarPlanta"
								use:enhance={() => {
									procesando = true;
									return async ({ update, result }) => {
										await update();
										procesando = false;
										if (result.type === 'success') {
											modalAbierto = false;
										}
									};
								}}
							>
								<div class="field mb-3">
									<label class="label is-small" for="operador-rearme">Operador Responsable de Turno</label>
									<div class="control has-icons-left">
										<input
											id="operador-rearme"
											name="operador"
											class="input is-small"
											type="text"
											bind:value={operador}
											required
										/>
										<span class="icon is-small is-left">
											<i class="fa-solid fa-user-check"></i>
										</span>
									</div>
								</div>

								<div class="field mb-4">
									<label class="label is-small" for="motivo-rearme">Causa de Rearme y Verificación</label>
									<div class="control has-icons-left">
										<input
											id="motivo-rearme"
											name="motivo"
											class="input is-small"
											type="text"
											value="Verificación física completada. Rearme operativo desde estación SCADA."
											required
										/>
										<span class="icon is-small is-left">
											<i class="fa-solid fa-clipboard-check"></i>
										</span>
									</div>
								</div>

								<footer class="is-flex is-justify-content-flex-end" style="gap: 0.75rem;">
									<AlertDialog.Cancel class="button is-light has-text-weight-semibold">
										Cancelar
									</AlertDialog.Cancel>
									<button
										type="submit"
										class="button is-success has-text-weight-bold {procesando ? 'is-loading' : ''}"
									>
										<i class="fa-solid fa-play mr-2"></i> Confirmar Rearme de Planta
									</button>
								</footer>
							</form>
						</div>
					</AlertDialog.Content>
				</AlertDialog.Portal>
			</AlertDialog.Root>
		</div>
	{:else}
		<div class="card p-4 stop-card mb-4">
			<div class="columns is-vcentered">
				<div class="column is-8">
					<div class="is-flex is-align-items-center mb-1">
						<span class="tag is-danger is-light has-text-weight-bold mr-2 is-family-code">
							SEGURIDAD FUNCIONAL
						</span>
						<span class="tag is-dark is-family-code">ISO 13849-1 vs HTTP</span>
					</div>
					<h3 class="title is-5 mb-1 has-text-dark">
						Solicitud Administrativa de Parada de Planta
					</h3>
					<p class="is-size-7 has-text-grey">
						Envía una consigna lógica asíncrona hacia el backend FastAPI para ordenar la desconexión
						controlada de actuadores y registrar la auditoría con estampilla de tiempo.
					</p>
				</div>

				<div class="column is-4 has-text-right-tablet">
					<AlertDialog.Root bind:open={modalAbierto}>
						<AlertDialog.Trigger class="button is-danger is-medium is-fullwidth has-text-weight-bold" style="box-shadow: 0 4px 14px rgba(220, 38, 38, 0.4);">
							<i class="fa-solid fa-hand mr-2"></i> PARO DE EMERGENCIA
						</AlertDialog.Trigger>

						<AlertDialog.Portal>
							<AlertDialog.Overlay class="scada-dialog-overlay" />
							<AlertDialog.Content class="scada-dialog-content">
								<header
									class="p-4 is-flex is-align-items-center"
									style="background:#fef2f2; border-bottom:1px solid #fecaca;"
								>
									<span class="tag is-danger is-large mr-3">
										<i class="fa-solid fa-triangle-exclamation"></i>
									</span>
									<div>
										<AlertDialog.Title class="title is-4 mb-0 has-text-danger-dark">
											Confirmar Parada Administrativa de Planta
										</AlertDialog.Title>
										<p class="is-size-7 has-text-grey">
											Acción de supervisión SCADA · Clase 7 (FIUNA)
										</p>
									</div>
								</header>

								<div class="p-4">
									<AlertDialog.Description class="is-size-6 mb-3">
										Esta acción enviará una solicitud inmediata a través de la API REST para ordenar
										el cese de operación de todos los lazos de control de la caldera y turbinas.
									</AlertDialog.Description>

									<!-- ADVERTENCIA METROLÓGICA Y DE SEGURIDAD FUNCIONAL -->
									<div class="notification is-danger is-light p-3 mb-4" style="border-left: 5px solid #dc2626;">
										<h4 class="title is-6 mb-1 has-text-danger-dark">
											<i class="fa-solid fa-shield-halved mr-1"></i>
											Fundamento Mecatrónico: ¿Por qué la Web NUNCA es Categoría 4 / PLe?
										</h4>
										<p class="is-size-7 mb-2">
											En seguridad industrial certificada (<strong>ISO 13849-1 / IEC 62061</strong>), un paro
											de emergencia de <strong>Categoría 4 / PLe</strong> exige:
										</p>
										<ul class="is-size-7 mb-2 ml-4" style="list-style-type: disc;">
											<li>
												<strong>Lazo de hardware cableado redundante (2 canales NC):</strong>
												Apertura electromecánica directa de contactores en t &lt; 20 ms, sin software ni CPU en el camino crítico.
											</li>
											<li>
												<strong>Ausencia de determinismo en la Web:</strong>
												Este botón web cursa por navegador single-thread, Wi-Fi/Ethernet, buffers del SO y HTTP/TCP. Puede sufrir jitter de red, pérdidas de paquetes o bloqueo del servidor.
											</li>
										</ul>
										<p class="is-size-7 has-text-weight-bold has-text-danger-dark">
											⚠️ En planta física real, la seta de emergencia de doble canal en el pupitre es la única legalmente válida para salvar vidas humanas.
										</p>
									</div>

									<!-- Formulario con use:enhance de SvelteKit -->
									<form
										method="POST"
										action="?/paroEmergencia"
										use:enhance={() => {
											procesando = true;
											return async ({ update, result }) => {
												await update();
												procesando = false;
												if (result.type === 'success') {
													modalAbierto = false;
												}
											};
										}}
									>
										<div class="field mb-3">
											<label class="label is-small" for="operador-paro">Operador Solicitante</label>
											<div class="control has-icons-left">
												<input
													id="operador-paro"
													name="operador"
													class="input is-small"
													type="text"
													bind:value={operador}
													required
												/>
												<span class="icon is-small is-left">
													<i class="fa-solid fa-user-shield"></i>
												</span>
											</div>
										</div>

										<div class="field mb-4">
											<label class="label is-small" for="motivo-paro">Motivo / Incidencia Detectada</label>
											<div class="control has-icons-left">
												<input
													id="motivo-paro"
													name="motivo"
													class="input is-small"
													type="text"
													bind:value={motivo}
													required
												/>
												<span class="icon is-small is-left">
													<i class="fa-solid fa-triangle-exclamation"></i>
												</span>
											</div>
										</div>

										<footer class="is-flex is-justify-content-flex-end" style="gap: 0.75rem;">
											<AlertDialog.Cancel class="button is-light has-text-weight-semibold">
												Cancelar y Volver
											</AlertDialog.Cancel>
											<button
												type="submit"
												class="button is-danger has-text-weight-bold {procesando ? 'is-loading' : ''}"
											>
												<i class="fa-solid fa-skull-crossbones mr-2"></i> Ejecutar Paro Administrativo
											</button>
										</footer>
									</form>
								</div>
							</AlertDialog.Content>
						</AlertDialog.Portal>
					</AlertDialog.Root>
				</div>
			</div>

			<!-- Visualización de Latencia RTT si se acaba de disparar una acción -->
			{#if latenciaRttMs !== null}
				<div class="mt-3 p-3 is-size-7" style="background:#f1f5f9; border-radius:6px; border:1px solid #cbd5e1;">
					<span class="has-text-weight-bold has-text-link">
						<i class="fa-solid fa-stopwatch mr-1"></i> RTT Medido en la última acción:
					</span>
					<span class="tag is-info is-family-code ml-1">{latenciaRttMs} ms</span>
					<span class="has-text-grey ml-2">
						(Navegador → SvelteKit BFF → FastAPI HTTP → Retorno). En un relé de Categoría 4 por hardware el tiempo de conmutación es &lt; 20 ms garantizado por resorte mecánico.
					</span>
				</div>
			{/if}
		</div>
	{/if}
</div>

<style>
	.emergency-trigger-box {
		width: 100%;
	}

	.stop-card {
		border: 1px solid #fca5a5;
		background: #fffafa;
		border-radius: 10px;
	}

	.paro-pulse-banner {
		background: #dc2626 !important;
		border-radius: 10px;
		animation: pulse-danger-banner 1.5s infinite;
	}

	@keyframes pulse-danger-banner {
		0%, 100% { box-shadow: 0 0 0 0 rgba(220, 38, 38, 0.7); }
		50% { box-shadow: 0 0 0 8px rgba(220, 38, 38, 0.2); }
	}

	:global(.scada-dialog-overlay) {
		position: fixed;
		inset: 0;
		background-color: rgba(15, 23, 42, 0.75);
		backdrop-filter: blur(4px);
		z-index: 9998;
		animation: scadaFadeIn 0.15s ease-out;
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
		animation: scadaScaleUp 0.18s cubic-bezier(0.16, 1, 0.3, 1);
	}

	@keyframes scadaFadeIn {
		from { opacity: 0; }
		to { opacity: 1; }
	}

	@keyframes scadaScaleUp {
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
