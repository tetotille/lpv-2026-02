import { FASTAPI_BASE_URL } from '$lib/config.js';
import { error, fail } from '@sveltejs/kit';

/**
 * +page.server.js (Ruta Dinámica /sensores/[id])
 * Carga el estado metrológico del transductor específico exclusivamente desde FastAPI.
 *
 * Cátedra: Lenguajes de Programación Visual — FIUNA
 */
export async function load({ params, fetch }) {
	const sensorId = params.id?.toUpperCase();

	try {
		const controller = new AbortController();
		const timeout = setTimeout(() => controller.abort(), 2000);

		// Petición al detalle individual del sensor en FastAPI
		const resSensor = await fetch(`${FASTAPI_BASE_URL}/api/sensores/${sensorId}`, {
			signal: controller.signal
		});

		if (resSensor.status === 404) {
			clearTimeout(timeout);
			throw error(404, `Transductor "${sensorId}" no encontrado en el sistema de instrumentación de la planta`);
		}

		if (!resSensor.ok) {
			clearTimeout(timeout);
			throw new Error(`FastAPI respondió con código HTTP ${resSensor.status}`);
		}

		const jsonSensor = await resSensor.json();

		// Petición al catálogo real de sensores activos en FastAPI para la navegación de nodos
		const resTodos = await fetch(`${FASTAPI_BASE_URL}/api/sensores`, {
			signal: controller.signal
		});
		clearTimeout(timeout);

		let sensoresDisponibles = [];
		if (resTodos.ok) {
			const jsonTodos = await resTodos.json();
			sensoresDisponibles = jsonTodos.sensores || [];
		}

		return {
			fastapiOnline: true,
			sensorId,
			sensor: jsonSensor.sensor || jsonSensor,
			historial: jsonSensor.historial || [],
			estadisticas: jsonSensor.estadisticas || {
				minimo: 0,
				maximo: 0,
				promedio: 0,
				total_muestras: 0
			},
			sensoresDisponibles
		};
	} catch (err) {
		// Si es un error 404 de SvelteKit explícito, relanzarlo
		if (err.status === 404) {
			throw err;
		}

		// Si FastAPI no está disponible, retornar estado offline sin ningún dato inventado
		return {
			fastapiOnline: false,
			sensorId,
			errorConexion: `No se pudo conectar con el servidor FastAPI en ${FASTAPI_BASE_URL}: ${err.message}`,
			sensor: null,
			historial: [],
			estadisticas: null,
			sensoresDisponibles: []
		};
	}
}

export const actions = {
	/**
	 * Form Action: Calibración Remota del Sensor
	 * Ajusta el offset de cero, umbral superior de alarma y tasa de muestreo exclusivamente en FastAPI.
	 */
	calibrar: async ({ params, request, fetch }) => {
		const sensorId = params.id?.toUpperCase();
		const formData = await request.formData();

		const offset = parseFloat(formData.get('offset') ?? '0');
		const rango_max = parseFloat(formData.get('rango_max') ?? '100');
		const frecuencia_muestreo_hz = parseInt(formData.get('frecuencia_muestreo_hz') ?? '10', 10);

		if (isNaN(offset) || isNaN(rango_max) || isNaN(frecuencia_muestreo_hz)) {
			return fail(400, {
				success: false,
				mensaje: 'Todos los parámetros de calibración deben ser números válidos.'
			});
		}

		if (rango_max <= 0) {
			return fail(400, {
				success: false,
				mensaje: 'El límite superior de alarma (rango_max) debe ser estrictamente mayor a cero.'
			});
		}

		try {
			const res = await fetch(`${FASTAPI_BASE_URL}/api/sensores/${sensorId}/calibrar`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ offset, rango_max, frecuencia_muestreo_hz })
			});

			if (!res.ok) {
				const errJson = await res.json().catch(() => ({}));
				return fail(res.status, {
					success: false,
					mensaje: errJson.detail || `Error al guardar calibración en el nodo ${sensorId}`
				});
			}

			const data = await res.json();

			return {
				success: true,
				mensaje: data.mensaje || `Parámetros de calibración para ${sensorId} grabados en memoria EEPROM.`,
				sensorActualizado: data.sensor || {
					id: sensorId,
					offset,
					rango_max,
					frecuencia_muestreo_hz
				}
			};
		} catch (err) {
			return fail(503, {
				success: false,
				mensaje: `Error al comunicar con el servidor FastAPI (${FASTAPI_BASE_URL}): ${err.message}`
			});
		}
	}
};
