# Rising Battle 2.0.1 — Diagnósticos y protección ante desync

- Envío automático de resúmenes técnicos al confirmarse un desync, activado por defecto y desactivable en Ajustes → Diagnósticos.
- Botón «Enviar diagnósticos anteriores» para revisar sesiones ya guardadas. Requiere confirmación en ese PC y evita duplicados.
- Los informes contienen versiones, huellas de datos/parches, reglas, conexión y primer frame divergente. No envían chats, rutas, ISO, memory ni archivos completos del juego.
- Panel privado del equipo BTC para comparar ambos lados. Personaje y técnica aún no se capturan automáticamente.
- Ranked: se corrige la derrota prematura que podía asignarse al cerrar el juego después de un desync, antes de recibir el aviso del rival. Si ambos confirman fallo, el set se anula sin puntos ni abandono. Los abandonos normales mantienen su penalización; un aviso unilateral de fallo no basta para anular el set.
- Motor BTC incluido fijo en 0.1.38.1. Se conservan datos modificados BTC, reglas FT2 / 360 s / máximo 2 personajes, payload de combate y diseño aprobado.

## Instalación y actualización

Extrae el ZIP y ejecuta Competitive Loader.exe, o usa Buscar actualizaciones en el cliente anterior. El ZIP no incluye ISO, memory, perfiles ni credenciales.

Si tu instalación todavía usa el motor 0.1.35.x del Loader 1.5.9, prepara una instalación nueva desde tu propia ISO en otra carpeta. Actualizar el EXE del Loader no migra ese motor antiguo automáticamente.

## Estado de verificación

132 pruebas Python locales y suites del servicio aprobadas. EXE comprobados en Windows. Servicio y panel privado verificados con una subida histórica real; la prueba de desync nuevo entre dos PCs queda pendiente. La corrección ranked tiene una prueba de regresión que falla antes y pasa después del arreglo. Los diagnósticos ayudan a investigar las causas; no identifican automáticamente el ataque exacto.
