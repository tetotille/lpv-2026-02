/**
 * Web Worker: Generador de Carga de Sensores Mecatrónicos
 * Simula la adquisición en Tiempo Real Físico de un sensor inercial (IMU MPU6050)
 * acoplado a un rotor industrial y un encoder incremental de cuadratura.
 *
 * Cátedra: Lenguajes de Programación Visual (LPV) - FIUNA
 * Proyecto 1: "El Banco de Estrés" (Límite Físico vs. Límite de Renderizado)
 */

let activo = false;
let timerId = null;
let frecuenciaHz = 100;
let contadorId = 0;
let pasosEncoderAcumulados = 0;

// Configuración del reloj de emisión en el hilo de fondo
const TICK_INTERVAL_MS = 10; // 10 ms = 100 ticks por segundo
const FREQ_FUNDAMENTAL_HZ = 28.5; // ~1710 RPM (desbalance rotatorio principal)
const FREQ_ARMONICO_HZ = 114.0; // 4x armónico de rodamiento (pista defectuosa)
const FREQ_RESONANCIA_HZ = 240.0; // Resonancia estructural de bancada

/**
 * Modela la señal física del acelerómetro MEMS triaxial MPU6050
 * Combinación de vibración mecánica multieje + armónicos + ruido térmico
 *
 * @param {number} tSegundos - Tiempo continuo simulado en segundos
 */
function calcularSenalFisica(tSegundos) {
	// 1. Armónico fundamental de desbalance rotatorio
	const senalFundamental = Math.sin(2 * Math.PI * FREQ_FUNDAMENTAL_HZ * tSegundos) * 1.85;

	// 2. Armónico secundario por degradación de pistas de rodamiento
	const senalArmonico = Math.sin(2 * Math.PI * FREQ_ARMONICO_HZ * tSegundos) * 0.75;

	// 3. Resonancia estructural de alta frecuencia
	const senalResonancia = Math.sin(2 * Math.PI * FREQ_RESONANCIA_HZ * tSegundos) * 0.35;

	// 4. Ruido gaussiano/estocástico del ADC del sensor
	const ruidoBlanco = (Math.random() - 0.5) * 0.45;

	// Aceleración instantánea total en Gs (-4G a +4G)
	const aceleracionG = senalFundamental + senalArmonico + senalResonancia + ruidoBlanco;

	// Velocidad angular del rotor (1710 RPM nominal con perturbación de par motor)
	const velocidadRpm = 1710 + Math.sin(2 * Math.PI * 1.2 * tSegundos) * 35 + (Math.random() - 0.5) * 10;

	// Encoder incremental: 1024 pulsos por revolución (16 pulsos promedio por avance de muestra)
	const deltaPasos = Math.max(1, Math.round((velocidadRpm / 60) * (1024 / Math.max(1, frecuenciaHz))));
	pasosEncoderAcumulados = (pasosEncoderAcumulados + deltaPasos) % 65536;

	return {
		aceleracionG: Number(aceleracionG.toFixed(3)),
		velocidadRpm: Number(velocidadRpm.toFixed(1)),
		pasosEncoder: pasosEncoderAcumulados
	};
}

/**
 * Ejecuta un tick del temporizador emitiendo la ráfaga calculada
 * para alcanzar la tasa objetivo de 100 Hz, 250 Hz, 500 Hz o 1000 Hz.
 */
function ejecutarTick() {
	if (!activo) return;

	// Con setInterval cada 10 ms (100 ticks/seg):
	// - 100 Hz  -> 1 muestra/tick  * 100 = 100 msgs/seg
	// - 250 Hz  -> 3 muestras/tick * 100 ≈ 250-300 msgs/seg
	// - 500 Hz  -> 5 muestras/tick * 100 = 500 msgs/seg
	// - 1000 Hz -> 10 muestras/tick * 100 = 1000 msgs/seg
	const muestrasPorTick = Math.max(1, Math.round(frecuenciaHz / 100));

	for (let i = 0; i < muestrasPorTick; i++) {
		contadorId++;
		const tRelativo = contadorId / frecuenciaHz;
		const fisica = calcularSenalFisica(tRelativo);

		self.postMessage({
			tipo: 'MUESTRA',
			payload: {
				id: contadorId,
				timestamp: performance.now(),
				tRelativo: Number(tRelativo.toFixed(4)),
				aceleracionG: fisica.aceleracionG,
				velocidadRpm: fisica.velocidadRpm,
				pasosEncoder: fisica.pasosEncoder
			}
		});
	}
}

function iniciar() {
	if (activo) return;
	activo = true;
	if (timerId) clearInterval(timerId);
	timerId = setInterval(ejecutarTick, TICK_INTERVAL_MS);
	self.postMessage({ tipo: 'ESTADO', activo: true, frecuenciaHz });
}

function detener() {
	activo = false;
	if (timerId) {
		clearInterval(timerId);
		timerId = null;
	}
	self.postMessage({ tipo: 'ESTADO', activo: false, frecuenciaHz });
}

function cambiarFrecuencia(nuevaFrecuencia) {
	const f = Number(nuevaFrecuencia);
	if (!Number.isNaN(f) && f > 0) {
		frecuenciaHz = f;
		if (activo) {
			clearInterval(timerId);
			timerId = setInterval(ejecutarTick, TICK_INTERVAL_MS);
		}
		self.postMessage({ tipo: 'ESTADO', activo, frecuenciaHz });
	}
}

// Escucha de comandos desde el hilo principal
self.addEventListener('message', (evento) => {
	const data = evento.data || {};
	const comando = data.comando;

	switch (comando) {
		case 'INICIAR':
			if (data.frecuenciaHz) frecuenciaHz = Number(data.frecuenciaHz);
			iniciar();
			break;

		case 'DETENER':
			detener();
			break;

		case 'CAMBIAR_FRECUENCIA':
			cambiarFrecuencia(data.frecuenciaHz);
			break;

		case 'RESET':
			detener();
			contadorId = 0;
			pasosEncoderAcumulados = 0;
			self.postMessage({ tipo: 'RESET_CONFIRMADO', activo: false, frecuenciaHz });
			break;

		default:
			break;
	}
});
