<script>
	/**
	 * Visor pedagógico de código fuente con pestañas interactivas.
	 * Usa exclusivamente Svelte 5 Runes ($props, $state).
	 */
	let { titulo = 'Código Fuente del Laboratorio', archivos = [] } = $props();

	let indiceActivo = $state(0);
	let copiado = $state(false);

	const archivoActual = $derived(archivos[indiceActivo] || archivos[0] || null);

	async function copiarCodigo() {
		if (!archivoActual?.codigo) return;
		try {
			await navigator.clipboard.writeText(archivoActual.codigo);
			copiado = true;
			setTimeout(() => {
				copiado = false;
			}, 1800);
		} catch {
			copiado = false;
		}
	}
</script>

{#if archivos.length > 0}
	<div class="card mt-5" style="border: 1px solid #cbd5e1; border-radius: 10px; overflow: hidden;">
		<header
			class="card-header is-align-items-center px-4 py-2"
			style="background-color: #f1f5f9; border-bottom: 1px solid #cbd5e1;"
		>
			<div class="is-flex is-align-items-center is-flex-grow-1" style="flex-wrap: wrap; gap: 0.5rem;">
				<span class="tag is-dark is-family-code">
					<i class="fa-solid fa-code mr-2 has-text-warning"></i>
					{titulo}
				</span>
				<div class="buttons has-addons mb-0">
					{#each archivos as arch, idx (arch.nombre)}
						<button
							type="button"
							class="button is-small {indiceActivo === idx
								? 'is-link has-text-weight-bold'
								: 'is-white'}"
							onclick={() => (indiceActivo = idx)}
						>
							<i class="fa-regular fa-file-code mr-1"></i>
							{arch.nombre}
						</button>
					{/each}
				</div>
			</div>

			<button type="button" class="button is-small is-light" onclick={copiarCodigo}>
				{#if copiado}
					<i class="fa-solid fa-check has-text-success mr-1"></i> Copiado
				{:else}
					<i class="fa-regular fa-copy mr-1"></i> Copiar
				{/if}
			</button>
		</header>

		{#if archivoActual?.descripcion}
			<div
				class="px-4 py-2 is-size-7"
				style="background-color: #eff6ff; color: #1e3a8a; border-bottom: 1px solid #dbeafe;"
			>
				<i class="fa-solid fa-graduation-cap mr-1"></i>
				<strong>Nota de Cátedra:</strong>
				{archivoActual.descripcion}
			</div>
		{/if}

		<div class="code-box" style="border-radius: 0; border: none;">
			<pre><code>{archivoActual?.codigo || ''}</code></pre>
		</div>
	</div>
{/if}
