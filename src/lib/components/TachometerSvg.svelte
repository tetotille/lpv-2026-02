<script>
	/**
	 * TachometerSvg.svelte — Instrumento vectorial circular de alta precisión.
	 * Cátedra: Lenguajes de Programación Visual (FIUNA) — Clase 7: Tiempo Real Físico vs. Administrativo
	 *
	 * Desacopla visualmente dos realidades temporales:
	 * 1. Aguja 1 (Azul): Consigna Administrativa del Operador r(t) -> respuesta instantánea (transition: none).
	 * 2. Aguja 2 (Roja): Realimentación Física del Rotor y(t) -> amortiguación CSS según inercia mecánica.
	 * 3. Sector de Discrepancia: Resalta la brecha angular e(t) = r(t) - y(t).
	 */

	let {
		consigna = 0,
		valorReal = 0,
		maxRpm = 3000,
		unidad = 'RPM',
		amortiguacionCssMs = 60
	} = $props();

	// Centro geométrico y radio base del instrumento (viewBox: 0 0 340 300)
	const cx = 170;
	const cy = 165;
	const rExterior = 124;

	// Conversión de RPM a grados angulares: 0..3000 RPM -> -135° a +135° (270° de barrido)
	function rpmAAngulo(rpm) {
		const clamped = Math.min(Math.max(rpm, -150), maxRpm * 1.15);
		return -135 + (clamped / maxRpm) * 270;
	}

	const anguloConsigna = $derived(rpmAAngulo(consigna));
	const anguloReal = $derived(rpmAAngulo(valorReal));

	// Función trigonométrica polar a cartesiana (0° = 12 en punto / vertical arriba)
	function polarACartesiano(centroX, centroY, radio, anguloDeg) {
		const rad = ((anguloDeg - 90) * Math.PI) / 180;
		return {
			x: centroX + radio * Math.cos(rad),
			y: centroY + radio * Math.sin(rad)
		};
	}

	// Generador de sector anular SVG en coordenadas de pantalla
	function describirArcoBanda(centroX, centroY, rIn, rOut, anguloInicio, anguloFin) {
		const diff = anguloFin - anguloInicio;
		if (diff <= 0.2) return '';
		const largeArc = diff > 180 ? 1 : 0;

		const p1 = polarACartesiano(centroX, centroY, rOut, anguloInicio);
		const p2 = polarACartesiano(centroX, centroY, rOut, anguloFin);
		const p3 = polarACartesiano(centroX, centroY, rIn, anguloFin);
		const p4 = polarACartesiano(centroX, centroY, rIn, anguloInicio);

		return `M ${p1.x.toFixed(2)} ${p1.y.toFixed(2)} A ${rOut} ${rOut} 0 ${largeArc} 1 ${p2.x.toFixed(2)} ${p2.y.toFixed(2)} L ${p3.x.toFixed(2)} ${p3.y.toFixed(2)} A ${rIn} ${rIn} 0 ${largeArc} 0 ${p4.x.toFixed(2)} ${p4.y.toFixed(2)} Z`;
	}

	// Arcos estáticos de la escala: zona nominal (0 a 2500 RPM) y sobrevelocidad (2500 a 3000 RPM)
	const pathPistaNominal = $derived(describirArcoBanda(cx, cy, 116, 124, -135, 90));
	const pathPistaSobrecarga = $derived(describirArcoBanda(cx, cy, 114, 124, 90, 135));

	// Generación reactiva de marcas (ticks cada 250 RPM, etiquetas numéricas cada 500 RPM)
	const ticks = $derived.by(() => {
		const valores = [0, 250, 500, 750, 1000, 1250, 1500, 1750, 2000, 2250, 2500, 2750, 3000];
		return valores.map((val) => {
			const ang = -135 + (val / maxRpm) * 270;
			const esMayor = val % 500 === 0;
			const esCritico = val >= 2500;
			const rInterno = esMayor ? 107 : 115;
			const pExt = polarACartesiano(cx, cy, rExterior, ang);
			const pInt = polarACartesiano(cx, cy, rInterno, ang);
			const pTexto = polarACartesiano(cx, cy, 94, ang);

			return {
				val,
				ang,
				esMayor,
				esCritico,
				x1: pInt.x,
				y1: pInt.y,
				x2: pExt.x,
				y2: pExt.y,
				tx: pTexto.x,
				ty: pTexto.y
			};
		});
	});

	// Sector de Discrepancia Dinámica / Error de Lazo angular
	const anguloMin = $derived(Math.min(anguloConsigna, anguloReal));
	const anguloMax = $derived(Math.max(anguloConsigna, anguloReal));
	const pathDiscrepancia = $derived(describirArcoBanda(cx, cy, 88, 122, anguloMin, anguloMax));
	const errorRpm = $derived(Math.round(consigna - valorReal));
	const brechaAngularDeg = $derived(Math.abs(anguloConsigna - anguloReal));
</script>

<div class="tachometer-wrapper">
	<svg
		viewBox="0 0 340 300"
		class="tachometer-svg"
		role="img"
		aria-label="Tacómetro de precisión de doble aguja para supervisión mecatrónica"
	>
		<defs>
			<!-- Gradiente de fondo del dial tipo cockpit mecatrónico -->
			<radialGradient id="gradDialBg" cx="50%" cy="50%" r="50%">
				<stop offset="0%" stop-color="#1e293b" />
				<stop offset="85%" stop-color="#0f172a" />
				<stop offset="100%" stop-color="#020617" />
			</radialGradient>

			<!-- Gradiente para el bisel exterior metálico -->
			<linearGradient id="gradBisel" x1="0%" y1="0%" x2="100%" y2="100%">
				<stop offset="0%" stop-color="#64748b" />
				<stop offset="50%" stop-color="#1e293b" />
				<stop offset="100%" stop-color="#0f172a" />
			</linearGradient>

			<!-- Resplandor para el sector de discrepancia de lazo -->
			<filter id="glowDiscrepancia" x="-20%" y="-20%" width="140%" height="140%">
				<feGaussianBlur stdDeviation="3" result="blur" />
				<feComposite in="SourceGraphic" in2="blur" operator="over" />
			</filter>
		</defs>

		<!-- 1. Bisel y Fondo del Instrumento -->
		<circle cx={cx} cy={cy} r="136" fill="url(#gradBisel)" stroke="#475569" stroke-width="2" />
		<circle cx={cx} cy={cy} r="132" fill="url(#gradDialBg)" stroke="#334155" stroke-width="1.5" />
		<circle cx={cx} cy={cy} r="126" fill="none" stroke="#1e293b" stroke-width="1" />

		<!-- 2. Arcos de fondo graduados -->
		<!-- Pista nominal (0 - 2500 RPM) -->
		<path d={pathPistaNominal} fill="#334155" opacity="0.35" stroke="#475569" stroke-width="0.8" />

		<!-- Zona roja de sobrevelocidad (2500 - 3000 RPM) -->
		<path
			d={pathPistaSobrecarga}
			fill="#ef4444"
			opacity="0.45"
			stroke="#dc2626"
			stroke-width="1.6"
		/>

		<!-- 3. Sector de Discrepancia Temporal / Error de Lazo: e(t) = r(t) - y(t) -->
		{#if brechaAngularDeg > 0.4 && pathDiscrepancia}
			<path
				d={pathDiscrepancia}
				fill={consigna >= valorReal ? 'rgba(245, 158, 11, 0.38)' : 'rgba(239, 68, 68, 0.38)'}
				stroke={consigna >= valorReal ? '#f59e0b' : '#ef4444'}
				stroke-width="1.8"
				stroke-dasharray="4 2"
				filter="url(#glowDiscrepancia)"
			/>
		{/if}

		<!-- 4. Graduación: Ticks y Etiquetas Numéricas cada 500 RPM -->
		{#each ticks as tick (tick.val)}
			<line
				x1={tick.x1.toFixed(2)}
				y1={tick.y1.toFixed(2)}
				x2={tick.x2.toFixed(2)}
				y2={tick.y2.toFixed(2)}
				stroke={tick.esCritico ? '#ef4444' : tick.esMayor ? '#e2e8f0' : '#64748b'}
				stroke-width={tick.esMayor ? '2' : '1.1'}
				stroke-linecap="round"
			/>

			{#if tick.esMayor}
				<text
					x={tick.tx.toFixed(2)}
					y={tick.ty.toFixed(2)}
					text-anchor="middle"
					dominant-baseline="central"
					fill={tick.esCritico ? '#f87171' : '#cbd5e1'}
					font-size="9.5"
					font-weight="700"
					font-family="monospace"
				>
					{tick.val}
				</text>
			{/if}
		{/each}

		<!-- Etiqueta de zona roja crítica -->
		<text
			x="240"
			y="108"
			text-anchor="middle"
			fill="#ef4444"
			font-size="7.5"
			font-weight="bold"
			font-family="sans-serif"
			letter-spacing="0.8"
		>
			SOBREVELOCIDAD
		</text>

		<!-- Texto identificador central del instrumento -->
		<text
			x={cx}
			y="114"
			text-anchor="middle"
			fill="#64748b"
			font-size="9"
			font-family="sans-serif"
			font-weight="700"
			letter-spacing="1.2"
		>
			ROTOR MECHATRONICS
		</text>
		<text
			x={cx}
			y="127"
			text-anchor="middle"
			fill="#475569"
			font-size="8"
			font-family="monospace"
		>
			0 - {maxRpm} {unidad}
		</text>
		<text
			x={cx}
			y="208"
			text-anchor="middle"
			fill="#94a3b8"
			font-size="11"
			font-family="monospace"
			font-weight="700"
		>
			{unidad}
		</text>

		<!-- 5. AGUJA 1 — Consigna Administrativa (Azul #2563eb): Instantánea en el DOM -->
		<g
			class="needle-consigna"
			style="transform: rotate({anguloConsigna}deg); transform-origin: {cx}px {cy}px; transition: none;"
		>
			<!-- Varilla estilizada azul con flecha direccional en la punta -->
			<line
				x1={cx}
				y1={cy}
				x2={cx}
				y2="38"
				stroke="#2563eb"
				stroke-width="2.6"
				stroke-linecap="round"
			/>
			<polygon points="{cx - 4.5},48 {cx + 4.5},48 {cx},33" fill="#2563eb" />
			<circle cx={cx} cy="38" r="3.2" fill="#60a5fa" stroke="#1d4ed8" stroke-width="1" />
		</g>

		<!-- 6. AGUJA 2 — Realimentación Física del Sensor (Roja #dc2626): Amortiguada por CSS -->
		<g
			class="needle-real"
			style="transform: rotate({anguloReal}deg); transform-origin: {cx}px {cy}px; transition: transform {amortiguacionCssMs}ms linear;"
		>
			<!-- Hoja cónica con contrapeso de inercia y alma luminosa -->
			<polygon
				points="{cx - 4},165 {cx - 1.4},52 {cx},42 {cx + 1.4},52 {cx + 4},165 {cx + 2.5},188 {cx - 2.5},188"
				fill="#dc2626"
				stroke="#991b1b"
				stroke-width="1"
			/>
			<circle cx={cx} cy="180" r="4.5" fill="#7f1d1d" stroke="#fca5a5" stroke-width="0.8" />
			<line
				x1={cx}
				y1="184"
				x2={cx}
				y2="46"
				stroke="#fca5a5"
				stroke-width="0.9"
				opacity="0.8"
			/>
		</g>

		<!-- 7. Cojinete Central Metálico / Pivot sobre las agujas -->
		<circle cx={cx} cy={cy} r="13" fill="#0f172a" stroke="#475569" stroke-width="2.4" />
		<circle cx={cx} cy={cy} r="7.5" fill="#1e293b" stroke="#94a3b8" stroke-width="1.2" />
		<circle cx={cx} cy={cy} r="3.5" fill="#dc2626" />
		<circle cx={cx} cy={cy} r="1.2" fill="#ffffff" />

		<!-- 8. Lectura Digital Doble en la Base del Instrumento -->
		<g class="digital-readout">
			<!-- Panel contenedor de lectura digital -->
			<rect
				x="36"
				y="226"
				width="268"
				height="62"
				rx="8"
				fill="#090d16"
				stroke="#334155"
				stroke-width="1.5"
			/>

			<!-- Fila 1: SETPOINT (Consigna Azul) -->
			<circle cx="50" cy="245" r="4" fill="#2563eb" />
			<text x="60" y="248" fill="#94a3b8" font-size="10" font-family="monospace" font-weight="600">
				SETPOINT:
			</text>
			<text x="135" y="248" fill="#38bdf8" font-size="11.5" font-family="monospace" font-weight="700">
				{consigna} {unidad}
			</text>

			<!-- Fila 2: PLANTA REAL (Realimentación Roja) -->
			<circle cx="50" cy="268" r="4" fill="#dc2626" />
			<text x="60" y="271" fill="#94a3b8" font-size="10" font-family="monospace" font-weight="600">
				PLANTA REAL:
			</text>
			<text x="135" y="271" fill="#f87171" font-size="11.5" font-family="monospace" font-weight="700">
				{Math.round(valorReal)} {unidad}
			</text>

			<!-- Fila 3 Lateral: ERROR e(t) y ángulo de discrepancia -->
			<text x="290" y="246" text-anchor="end" fill="#94a3b8" font-size="8.5" font-family="monospace">
				ERROR e(t)
			</text>
			<text
				x="290"
				y="269"
				text-anchor="end"
				fill={Math.abs(errorRpm) > 15 ? '#fbbf24' : '#4ade80'}
				font-size="13"
				font-family="monospace"
				font-weight="700"
			>
				{errorRpm > 0 ? '+' : ''}{errorRpm}
			</text>
			<text x="290" y="280" text-anchor="end" fill="#64748b" font-size="7.5" font-family="monospace">
				Δθ: {brechaAngularDeg.toFixed(1)}°
			</text>
		</g>
	</svg>
</div>

<style>
	.tachometer-wrapper {
		width: 100%;
		max-width: 380px;
		margin: 0 auto;
		display: flex;
		flex-direction: column;
		align-items: center;
	}

	.tachometer-svg {
		width: 100%;
		height: auto;
		display: block;
		filter: drop-shadow(0 10px 18px rgba(15, 23, 42, 0.12));
		user-select: none;
	}

	/* La aguja roja aplica su amortiguación dinámica por transform CSS según amortiguacionCssMs */
	.needle-real {
		will-change: transform;
	}

	/* La aguja azul nunca debe tener transición para reflejar la consigna administrativa inmediata */
	.needle-consigna {
		transition: none !important;
		will-change: transform;
	}
</style>
