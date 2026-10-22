import { fail } from '@sveltejs/kit';
import { FASTAPI_BASE_URL } from '$lib/config.js';

/**
 * +page.server.js (Proyecto 7 / Admin 3: Matriz CapEx/OpEx y Mantenimiento Predictivo vs. Falla Catastrófica)
 *
 * Implementa el patrón Backend-For-Frontend (BFF) con auditoría estricta de desembolsos millonarios:
 * - load(): Recupera el catálogo de activos críticos, presupuesto anual CapEx y libro mayor de órdenes aprobadas desde FastAPI.
 * - actions.aprobarOrden: Emite la orden de compra adjuntando una clave de idempotencia única.
 *   FastAPI rechaza con HTTP 409 cualquier reintento o doble clic con la misma clave para impedir cobros dobles millonarios.
 *
 * SvelteKit 2 + Svelte 5 (Runes)
 * Cátedra: Lenguajes de Programación Visual — FIUNA
 */

export async function load({ fetch }) {
	try {
		const res = await fetch(`${FASTAPI_BASE_URL}/api/admin/capex`);
		if (!res.ok) {
			return {
				fastapiOnline: false,
				errorConexion: 'No se pudo conectar con FastAPI (' + FASTAPI_BASE_URL + '/api/admin/capex)'
			};
		}

		const capexData = await res.json();
		return {
			fastapiOnline: true,
			endpointConsultado: `${FASTAPI_BASE_URL}/api/admin/capex`,
			capexData
		};
	} catch (err) {
		return {
			fastapiOnline: false,
			errorConexion: 'No se pudo conectar con FastAPI (' + FASTAPI_BASE_URL + '/api/admin/capex)'
		};
	}
}

export const actions = {
	aprobarOrden: async ({ request, fetch }) => {
		const formData = await request.formData();
		const activo_id = formData.get('activo_id')?.toString() || '';
		const director_firmante = formData.get('director_firmante')?.toString() || '';
		const centro_costo = formData.get('centro_costo')?.toString() || '';
		const justificacion = formData.get('justificacion')?.toString() || '';
		const idempotency_key = formData.get('idempotency_key')?.toString() || '';

		try {
			const res = await fetch(`${FASTAPI_BASE_URL}/api/admin/capex/aprobar-orden`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					activo_id,
					director_firmante,
					centro_costo,
					justificacion,
					idempotency_key
				})
			});

			const body = await res.json().catch(() => ({}));

			if (!res.ok) {
				return fail(res.status, {
					error: body.detail || 'Error en FastAPI',
					codigoHttp: res.status,
					claveRechazada: idempotency_key
				});
			}

			return {
				success: true,
				respuesta: body
			};
		} catch (err) {
			return fail(500, {
				error: 'Error de conexión con el servidor FastAPI: ' + (err.message || 'desconocido'),
				codigoHttp: 500,
				claveRechazada: idempotency_key
			});
		}
	}
};
