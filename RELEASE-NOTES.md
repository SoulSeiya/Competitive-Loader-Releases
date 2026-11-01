# Rising Battle 2.0.3 — Estado de búsqueda ranked

- Corrige el mensaje «Comprobando la instalación para ranked» que permanecía en la barra inferior después de terminar la comprobación.
- La pantalla y la barra inferior muestran el estado actual: solicitando búsqueda, buscando rival compatible, rival encontrado o set en curso.
- Los errores del servicio aparecen aunque hubiera una clasificación cargada. Los errores locales de instalación permanecen visibles después de las consultas de fondo; no se envía una búsqueda si falla la validación.
- Conserva el bloqueo de Start en combate ranked de 2.0.2, el motor BTC fijo 0.1.38.1, la misma memory elegida por el jugador, los datos BTC, los parches y el CSS aprobado.

No hace falta reinstalar BTC. Esta corrección de interfaz es compatible con 2.0.2 si coinciden motor, memory y datos. No elimina las verificaciones de compatibilidad ni corrige por sí sola los desync del combate. No cambia puntos, temporada, reglas ni servicios.

Prueba de regresión del mensaje: falla antes del arreglo y pasa después. Pruebas de estados, errores y renderizado del EXE Windows incluidas. El render de búsqueda usa datos de prueba y no representa una partida humana nueva.

Actualiza desde el Loader o extrae el ZIP. No incluye ISO, memory, perfiles, credenciales ni registros personales.
