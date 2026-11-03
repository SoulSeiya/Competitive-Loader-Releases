# Rising Battle 2.1.1 — Puntos al completar una ranked reanudada

- Al completar el FT reanudado después de un desync confirmado por ambos, el perdedor no pierde Elo y recibe +6 puntos de ranked. Sustituye la pérdida normal y el bono separado de +3 de 2.1.0.
- El ganador conserva sus puntos Elo normales y el bono separado de +10 de juego limpio.
- Se aplica una sola vez. Los abandonos y las desconexiones sin resultado confirmado no conceden esta protección; una ranked normal conserva su cálculo anterior.
- La pantalla de continuación consulta la regla activa del servidor para explicar correctamente el resultado.
- No modifica resultados anteriores, reinicia puntos ni cambia las reglas FT2 / 360 s / 2 personajes. Motor BTC fijo 0.1.38.1, datos BTC y CSS conservados.

Prueba de regresión: falla con 2.1.0 (988 en vez de 1006 al perder una revancha completada partiendo de 1000) y pasa con el ajuste. La prueba de servicio usa SQLite local; falta validación en una nueva ranked humana entre dos PCs.

Requiere activar el ajuste en el servicio. No incluye ISO, memory, perfiles, credenciales ni registros personales.

---

# Rising Battle 2.1.0 — Diagnósticos y continuidad ranked

- El informe automático de desync reúne jugadores, personajes activos, número de traje, escenario inicial/actual y habilidades observadas cerca de la primera divergencia. Solo envía datos técnicos filtrados; no los TXT completos, ISO, memory ni perfiles. Puedes desactivarlo en Ajustes.
- Si ambos equipos confirman el mismo desync, pueden aceptar continuar la ranked con el último marcador confirmado por ambos. La pelea interrumpida no suma una victoria. Se abre una conexión nueva y se vuelve a seleccionar personajes. No restaura una pelea a mitad de un ataque.
- Al completar el FT reanudado se aplica Elo normal una sola vez y un bono separado de juego limpio: +10 al ganador y +3 al perdedor. Este bono no sube Elo. No se concede por salir, rechazar, agotar el plazo ni abandonar.
- Ambos deben usar esta versión. Hay 120 segundos para aceptar y un máximo de tres reanudaciones; los casos sin prueba coincidente quedan sin puntos. Los clientes anteriores conservan su comportamiento sin reanudación.
- Las próximas versiones del Loader se descargan y verifican en segundo plano. El botón principal muestra «Actualizar Loader»; la instalación y el reinicio requieren pulsarlo con el juego cerrado y sin ranked activa. El motor no se actualiza automáticamente.
- Conserva el motor BTC 0.1.38.1, los datos modificados, conjuntos personalizados, pausa contra CPU e intros saltables. Reglas ranked: FT2 / 360 s / 2 personajes.

Los datos cercanos al desync orientan la investigación: no demuestran que la última habilidad, el personaje o el mapa lo hayan causado.

Validación: pruebas automatizadas del registro, simulaciones de dos clientes contra SQLite y comprobación del render Windows. La continuación tras desync y el bono requieren todavía prueba humana en dos PCs; no se presentan como verificados en una partida real nueva.

No incluye ISO, memory, cuentas, credenciales ni registros de jugadores. No reinicia la clasificación ni añade torneos o espectador.
