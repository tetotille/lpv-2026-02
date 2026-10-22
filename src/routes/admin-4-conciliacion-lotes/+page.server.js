import { FASTAPI_BASE_URL } from '$lib/config.js';
import { fail } from '@sveltejs/kit';

/**
 * +page.server.js — Proyecto 8 (Admin 4):
 * Conciliación Contable de Lotes (MES vs. ERP), Mermas de Materia Prima y Auditoría Financiera
 *
 * Implementa el patrón Backend-For-Frontend (BFF) para Tiempo Real Administrativo:
 * - Carga en SSR consultando FastAPI con filtro por estado.
 * - Form Action `emitirDictamen` para auditoría técnica-financiera sin recarga de página.
 * - Cero fallbacks harcodeados: 100% dependiente de FastAPI (:8007).
 *
 * Cátedra: Lenguajes de Programación Visual — FIUNA
 */

export async function load({ url, fetch }) {
	const estado_filtro = url.searchParams.get('estado') || 'TODOS';
	const apiFiltro = estado_filtro === 'ANOMALIA' ? 'TODOS' : estado_filtro;
	const endpoint = `${FASTAPI_BASE_URL}/api/admin/conciliacion-lotes?estado_filtro=${encodeURIComponent(apiFiltro)}`;

	try {
		const controller = new AbortController();
		const timeout = setTimeout(() => controller.abort(), 3500);

		const res = await fetch(endpoint, {
			signal: controller.signal
		});
		clearTimeout(timeout);

		if (!res.ok) {
			return {
				fastapiOnline: false,
				errorConexion: `No se pudo conectar con FastAPI (${FASTAPI_BASE_URL}/api/admin/conciliacion-lotes)`
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
			endpointConsultado: `${FASTAPI_BASE_URL}/api/admin/conciliacion-lotes?estado_filtro=${estado_filtro}`,
			conciliacion
		};
	} catch (err) {
		return {
			fastapiOnline: false,
			errorConexion: `No se pudo conectar con FastAPI (${FASTAPI_BASE_URL}/api/admin/conciliacion-lotes)`
		};
	}
}

export const actions = {
	/**
	 * Form Action: Emitir Dictamen de Auditoría Financiera y Metrológica
	 * Envía la decisión a FastAPI para revalidar y congelar el lote en ERP o mandar a calibrar el caudalímetro.
	 */
	emitirDictamen: async ({ request, fetch }) => {
		const formData = await request.formData();
		const lote_id = formData.get('lote_id')?.toString() || '';
		const accion = formData.get('accion')?.toString() || 'APROBADO_CONFORME';
		const auditor = formData.get('auditor')?.toString() || 'Auditor Contable-Metrológico';
		const causa_raiz = formData.get('causa_raiz')?.toString() || 'Sin causa especificada';
		const observacion = formData.get('observacion')?.toString() || '';

		if (!lote_id) {
			return fail(400, {
				error: 'Debe especificar el identificador del lote (lote_id).'
			});
		}

		try {
			const res = await fetch(`${FASTAPI_BASE_URL}/api/admin/conciliacion-lotes/dictamen`, {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json'
				},
				body: JSON.stringify({
					lote_id,
					accion,
					auditor,
					causa_raiz,
					observacion
				})
			});

			const body = await res.json().catch(() => ({}));

			if (!res.ok) {
				return fail(res.status, {
					error: body.detail || 'Error al registrar dictamen en FastAPI'
				});
			}

			return {
				success: true,
				respuesta: body
			};
		} catch (err) {
			return fail(500, {
				error: `Error de conexión con FastAPI: ${err.message}`
			});
		}
	}
};
