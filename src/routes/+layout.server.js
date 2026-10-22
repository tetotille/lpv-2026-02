import { FASTAPI_BASE_URL } from '$lib/config.js';

/**
 * +layout.server.js
 * Verifica en SSR la disponibilidad del servidor obligatorio FastAPI (puerto 8000)
 * y provee metadatos globales a toda la jerarquía de rutas de la Clase 7.
 */
export async function load({ fetch }) {
	const horaServidorSvelteKit = new Date().toLocaleTimeString('es-PY', {
		hour12: false,
		hour: '2-digit',
		minute: '2-digit',
		second: '2-digit'
	});

	let fastapiOnline = false;
	let fastapiEstado = null;

	try {
		const controller = new AbortController();
		const timeout = setTimeout(() => controller.abort(), 1200);
		const res = await fetch(`${FASTAPI_BASE_URL}/api/health`, {
			signal: controller.signal
		});
		clearTimeout(timeout);

		if (res.ok) {
			fastapiOnline = true;
			fastapiEstado = await res.json();
		}
	} catch {
		fastapiOnline = false;
	}

	return {
		horaServidorSvelteKit,
		fastapiUrl: FASTAPI_BASE_URL,
		fastapiOnline,
		fastapiEstado
	};
}
