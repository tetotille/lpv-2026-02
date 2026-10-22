import { FASTAPI_BASE_URL } from '$lib/config.js';
import { fail } from '@sveltejs/kit';

/**
 * +page.server.js - Proyecto 6 (Admin 2):
 * Auditoría Energética y Pliego Tarifario ANDE (Horario Punta vs. Fuera de Punta y Penalización cos φ)
 *
 * Cátedra: Lenguajes de Programación Visual — FIUNA
 * Toda la auditoría tarifaria y cálculos en Guaraníes provienen del servidor FastAPI.
 */

export async function load({ fetch }) {
	try {
		const controller = new AbortController();
		const timeout = setTimeout(() => controller.abort(), 3000);
		const res = await fetch(`${FASTAPI_BASE_URL}/api/admin/energia-ande`, {
			signal: controller.signal
		});
		clearTimeout(timeout);

		if (!res.ok) {
			return {
				fastapiOnline: false,
				errorConexion:
					'No se pudo conectar con FastAPI (' +
					FASTAPI_BASE_URL +
					'/api/admin/energia-ande)'
			};
		}

		const datosAnde = await res.json();
		return {
			fastapiOnline: true,
			endpointConsultado: `${FASTAPI_BASE_URL}/api/admin/energia-ande`,
			datosAnde
		};
	} catch (err) {
		return {
			fastapiOnline: false,
			errorConexion:
				'No se pudo conectar con FastAPI (' +
				FASTAPI_BASE_URL +
				'/api/admin/energia-ande)'
		};
	}
}

export const actions = {
	simularTarifa: async ({ request, fetch }) => {
		const fd = await request.formData();
		const cos_phi_objetivo = Number(fd.get('cos_phi_objetivo') ?? 0.96);
		const pct_desplazamiento_punta = Number(fd.get('pct_desplazamiento_punta') ?? 35);
		const inversion_capacitores_gs = Number(fd.get('inversion_capacitores_gs') ?? 95000000);

		try {
			const res = await fetch(`${FASTAPI_BASE_URL}/api/admin/energia-ande/simular`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					cos_phi_objetivo,
					pct_desplazamiento_punta,
					inversion_capacitores_gs
				})
			});

			if (!res.ok) {
				const errorJson = await res.json().catch(() => ({}));
				return fail(res.status, {
					error: errorJson.detail || 'Error al simular pliego ANDE en FastAPI'
				});
			}

			const simulacion = await res.json();
			return {
				success: true,
				simulacion
			};
		} catch (err) {
			return fail(500, {
				error: 'Error de conexión con FastAPI al simular pliego ANDE: ' + err.message
			});
		}
	}
};
