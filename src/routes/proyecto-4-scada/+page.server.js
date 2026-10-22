import { FASTAPI_BASE_URL } from '$lib/config.js';

/**
 * +page.server.js (Proyecto 4: Dashboard SCADA Completo)
 * Implementa el patrón Backend-For-Frontend (BFF):
 * Realiza la carga inicial en SSR consultando FastAPI desde el servidor Node,
 * eliminando problemas de CORS en el navegador y entregando un primer render instantáneo.
 *
 * Cátedra: Lenguajes de Programación Visual — FIUNA
 */

export async function load({ fetch }) {
	try {
		const controller = new AbortController();
		const timeout = setTimeout(() => controller.abort(), 1500);

		const res = await fetch(`${FASTAPI_BASE_URL}/api/sensores`, {
			signal: controller.signal
		});
		clearTimeout(timeout);

		if (!res.ok) {
			throw new Error(`FastAPI respondió con código de estado HTTP ${res.status}`);
		}

		const json = await res.json();

		return {
			fastapiOnline: true,
			estadoPlanta: json.estado_planta || 'EN_MARCHA',
			sensoresIniciales: json.sensores || [],
			eventosIniciales: json.eventos_recientes || [],
			timestampSsr: new Date().toISOString()
		};
	} catch (err) {
		// Captura elegante ante desconexión o apagado de FastAPI
		return {
			fastapiOnline: false,
			estadoPlanta: 'DESCONECTADO',
			sensoresIniciales: [],
			eventosIniciales: [],
			errorConexion: 'No se pudo contactar a FastAPI en ' + FASTAPI_BASE_URL
		};
	}
}

export const actions = {
	/**
	 * Form Action: Paro de Emergencia Administrativo
	 * Mide el RTT del viaje de red y transmite la orden hacia FastAPI.
	 */
	paroEmergencia: async ({ request, fetch }) => {
		const formData = await request.formData();
		const motivo = formData.get('motivo') || 'Paro de emergencia administrativo desde SCADA Web';
		const operador = formData.get('operador') || 'Operador SCADA Turno A';

		const t0 = performance.now();
		let latenciaRttMs = 0;

		try {
			const res = await fetch(`${FASTAPI_BASE_URL}/api/planta/paro-emergencia`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ accion: 'PARAR', motivo, operador })
			});

			latenciaRttMs = Math.round(performance.now() - t0);

			if (!res.ok) {
				const errorJson = await res.json().catch(() => ({}));
				return {
					success: false,
					accion: 'PARAR',
					latenciaRttMs,
					error: errorJson.detail || `Error HTTP ${res.status} al solicitar paro`,
					timestamp: new Date().toISOString()
				};
			}

			const respuesta = await res.json();

			return {
				success: true,
				accion: 'PARAR',
				latenciaRttMs,
				respuesta,
				timestamp: new Date().toISOString()
			};
		} catch (err) {
			latenciaRttMs = Math.round(performance.now() - t0);
			return {
				success: false,
				accion: 'PARAR',
				latenciaRttMs,
				error: err.message,
				timestamp: new Date().toISOString()
			};
		}
	},

	/**
	 * Form Action: Restaurar Planta
	 * Rearma el sistema productivo tras verificación de condiciones seguras.
	 */
	restaurarPlanta: async ({ request, fetch }) => {
		const formData = await request.formData();
		const motivo = formData.get('motivo') || 'Rearme administrativo desde SCADA';
		const operador = formData.get('operador') || 'Operador Turno A';

		const t0 = performance.now();
		let latenciaRttMs = 0;

		try {
			const res = await fetch(`${FASTAPI_BASE_URL}/api/planta/paro-emergencia`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ accion: 'RESTAURAR', motivo, operador })
			});

			latenciaRttMs = Math.round(performance.now() - t0);

			if (!res.ok) {
				const errorJson = await res.json().catch(() => ({}));
				return {
					success: false,
					accion: 'RESTAURAR',
					latenciaRttMs,
					error: errorJson.detail || `Error HTTP ${res.status} al restaurar planta`,
					timestamp: new Date().toISOString()
				};
			}

			const respuesta = await res.json();

			return {
				success: true,
				accion: 'RESTAURAR',
				latenciaRttMs,
				respuesta,
				timestamp: new Date().toISOString()
			};
		} catch (err) {
			latenciaRttMs = Math.round(performance.now() - t0);
			return {
				success: false,
				accion: 'RESTAURAR',
				latenciaRttMs,
				error: err.message,
				timestamp: new Date().toISOString()
			};
		}
	}
};
