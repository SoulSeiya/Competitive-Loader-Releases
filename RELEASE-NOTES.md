# Rising Battle 2.0.2 — Start bloqueado en combate ranked

- Start se ignora durante los combates ranked activos para impedir abrir el menú de pausa y salir a selección en mitad de la pelea.
- El filtro actúa sobre ambos mandos y mantiene los demás botones. Selección de personajes, resultados, duelos casuales y offline conservan sus controles.
- Reconoce también ranked iniciada con el juego ya abierto desde el Loader.
- Se mantienen los diagnósticos automáticos de 2.0.1, motor BTC fijo 0.1.38.1, diseño aprobado y reglas FT2 / 360 segundos / máximo 2 personajes.

## Actualizar

Usa Buscar actualizaciones o descarga y extrae el ZIP. Ambos jugadores deben actualizar: el parche cambia la huella de compatibilidad y las búsquedas ranked de versiones distintas quedan separadas. No hace falta reinstalar los datos si ya usas el motor BTC 0.1.38.1.

Si todavía usas el motor 0.1.35.x del antiguo Loader 1.5.9, prepara una instalación nueva desde tu ISO en otra carpeta; actualizar el Loader no migra ese motor automáticamente.

## Verificación

Regresión nativa comprobada: falla antes del arreglo y pasa después, incluyendo ambos mandos y los modos que deben conservar Start. Suite Python local:132 pruebas, una omitida. Arranque real del EXE en Windows y contrato del parche contra el motor 0.1.38.1 comprobados; CSS aprobado idéntico. La prueba de una partida ranked real entre dos PCs con este parche está pendiente. No se han asignado puntos retroactivos al incidente reportado.

El paquete no incluye ISO, memory, perfiles, credenciales ni registros personales.
