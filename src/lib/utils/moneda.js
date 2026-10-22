/**
 * Utilidades de formateo monetario y contable para Guaraníes (PYG - ₲)
 * En Paraguay el Guaraní se opera contablemente sin céntimos (0 decimales).
 */

const formateadorPyg = new Intl.NumberFormat('es-PY', {
	maximumFractionDigits: 0
});

const formateadorDecimal = new Intl.NumberFormat('es-PY', {
	minimumFractionDigits: 1,
	maximumFractionDigits: 1
});

/**
 * Formatea un monto entero en Guaraníes con símbolo ₲ y separadores de miles con punto.
 * Ejemplo: 142500000 -> "₲ 142.500.000"
 * @param {number} monto
 * @returns {string}
 */
export function formatearGuaranies(monto) {
	if (monto === null || monto === undefined || Number.isNaN(Number(monto))) {
		return '₲ 0';
	}
	const valor = Math.round(Number(monto));
	const signo = valor < 0 ? '-' : '';
	return `${signo}₲ ${formateadorPyg.format(Math.abs(valor))}`;
}

/**
 * Formatea montos grandes expresados en millones de Guaraníes para ejes o KPIs compactos.
 * Ejemplo: 261400000 -> "₲ 261,4 M"
 * @param {number} monto
 * @returns {string}
 */
export function formatearMillonesGuaranies(monto) {
	if (monto === null || monto === undefined || Number.isNaN(Number(monto))) {
		return '₲ 0 M';
	}
	const millones = Number(monto) / 1_000_000;
	return `₲ ${formateadorDecimal.format(millones)} M`;
}
