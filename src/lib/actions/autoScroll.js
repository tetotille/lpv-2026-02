/**
 * Acción nativa de Svelte (use:autoScroll)
 * Desplaza automáticamente hacia el último evento un contenedor de logs SCADA
 * cuando se insertan nuevos nodos en el DOM, respetando si el operador pausó el scroll.
 *
 * @param {HTMLElement} node
 * @param {boolean} [enabled=true]
 */
export function autoScroll(node, enabled = true) {
	let activo = enabled;

	function scrollAlFinal() {
		if (activo && node) {
			node.scrollTop = node.scrollHeight;
		}
	}

	const observer = new MutationObserver(() => {
		scrollAlFinal();
	});

	observer.observe(node, { childList: true, subtree: true });
	scrollAlFinal();

	return {
		update(nuevoEstado) {
			activo = Boolean(nuevoEstado);
			if (activo) scrollAlFinal();
		},
		destroy() {
			observer.disconnect();
		}
	};
}
