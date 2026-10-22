import { FASTAPI_BASE_URL } from '$lib/config.js';
import { fail } from '@sveltejs/kit';

/**
 * +page.server.js — Proyecto 5 (Admin 1): OEE y Lucro Cesante en Millones de Guaraníes (₲)
 *
 * Implementa el patrón BFF (Backend-For-Frontend) de Tiempo Real Administrativo:
 * - Carga determinista e inmutable mediante SSR load() + URL SearchParams.
 * - Registro auditado de paradas con revalidación contable automática vía Form Actions.
 * - Toda la lógica financiera y de OEE reside estrictamente en FastAPI (backend Python).
 *
 * Cátedra: Lenguajes de Programación Visual — FIUNA
 */

export async function load({ url, fetch }) {
	const linea = url.searchParams.get('linea') || 'TODAS';
	const periodo = url.searchParams.get('periodo') || 'mes';
	const meta = url.searchParams.get('meta') || '85';

	const endpoint = `${FASTAPI_BASE_URL}/api/admin/oee?linea=${encodeURIComponent(linea)}&periodo=${encodeURIComponent(periodo)}&meta_disponibilidad=${encodeURIComponent(meta)}`;

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
				errorConexion: `No se pudo obtener el reporte OEE desde FastAPI (${FASTAPI_BASE_URL}/api/admin/oee)`,
				endpointConsultado: endpoint,
				filtros: { linea, periodo, meta: Number(meta) }
			};
		}

		const reporte = await res.json();

		return {
			fastapiOnline: true,
			endpointConsultado: `${FASTAPI_BASE_URL}/api/admin/oee?linea=${linea}&periodo=${periodo}&meta_disponibilidad=${meta}`,
			filtros: { linea, periodo, meta: Number(meta) },
			reporte
		};
	} catch (err) {
		return {
			fastapiOnline: false,
			errorConexion: `No se pudo obtener el reporte OEE desde FastAPI (${FASTAPI_BASE_URL}/api/admin/oee)`,
			endpointConsultado: endpoint,
			filtros: { linea, periodo, meta: Number(meta) }
		};
	}
}

export const actions = {
	/**
	 * Form Action: Imputar Paro Auditado y Recalcular Lucro Cesante en ₲
	 */
	registrarParo: async ({ request, fetch }) => {
		const formData = await request.formData();
		const linea = formData.get('linea')?.toString() || 'L1';
		const turno = formData.get('turno')?.toString() || 'Turno Mañana 06-14';
		const minutos = Number(formData.get('minutos')) || 0;
		const causa = formData.get('causa')?.toString() || 'Falla no especificada';
		const responsable = formData.get('responsable')?.toString() || 'Supervisor de Guardia';

		if (minutos <= 0) {
			return fail(400, {
				success: false,
				error: 'Los minutos de parada deben ser mayores a cero.',
				valores: { linea, turno, minutos, causa, responsable }
			});
		}

		try {
			const res = await fetch(`${FASTAPI_BASE_URL}/api/admin/oee/registrar-paro-auditado`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					linea,
					turno,
					minutos: Number(minutos),
					causa,
					responsable
				})
			});

			if (!res.ok) {
				const errorJson = await res.json().catch(() => ({}));
				return fail(res.status, {
					success: false,
					error: errorJson.detail || `Error HTTP ${res.status} al registrar el paro en FastAPI`,
					valores: { linea, turno, minutos, causa, responsable }
				});
			}

			const respuesta = await res.json();
			return {
				success: true,
				respuesta
			};
		} catch (err) {
			return fail(400, {
				success: false,
				error: `No se pudo conectar con FastAPI: ${err.message}`,
				valores: { linea, turno, minutos, causa, responsable }
			});
		}
	}
};
