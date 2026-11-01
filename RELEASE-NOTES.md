# Rising Battle 2.0.0 — Beta competitiva

Un cliente para jugar BTC: perfiles, amigos, salas y duelos desde una sola aplicación.

## Novedades
- Interfaz nueva, barra superior oscura y panel Amigos que puedes cerrar.
- Perfil local con nombre y foto; vinculación opcional con Challonge para importar la identidad.
- Amigos por código BTC, chat privado, invitaciones y desafíos mediante clic derecho. Los mensajes nuevos avisan junto al nombre del amigo.
- Solicitudes de duelo en pantalla con las reglas y botones Aceptar/Rechazar. Al aceptar se abre el juego.
- Salas públicas o con contraseña, chat y duelos entre miembros.
- Marcador FT compacto y transparente, presentación de combate y resultado GG.
- Ranked beta: FT2, 360 segundos y 2 personajes, elegidos dentro del juego. Nueva temporada desde 1000 puntos.
- Instalación desde tu propia ISO, motor BTC 0.1.38.1 incluido y registros locales para diagnosticar problemas.

## Actualizar desde el launcher anterior
Usa Buscar actualizaciones y acepta actualizar. Se sustituye el cliente; no se descarga automáticamente otra versión del decomp. Cierra el juego antes de actualizar.
Si tu instalación usa un motor anterior a 0.1.38.1, prepara una instalación nueva desde tu propia ISO y memory en la nueva interfaz. Conserva la instalación anterior hasta comprobar que todo funciona. No selecciones como destino una carpeta que ya contenga una instalación.
La actualización conserva el perfil/configuración local. En un PC nuevo, crea el perfil y prepara BTC; no se incluyen ISO ni memory.

## Alcance de esta beta
Torneos y espectador no están habilitados en esta entrega. La foto elegida en el perfil todavía se muestra localmente; compartir avatares entre clientes queda para una mejora posterior. Challonge es opcional y no habilita torneos aquí.
Los puntos ranked son provisionales. Elo por set: entre rivales con igual puntuación, normalmente +12/-12; el resultado 2-0 o 2-1 no cambia ese criterio.

## Validación y límites
120 pruebas Python y pruebas JavaScript de avisos pasadas. EXE y pantallas comprobados con datos simulados, incluyendo 820x600 sin desbordamiento. Hay duelos FT2 reales probados en versiones anteriores; falta repetir un ciclo online completo y la autorización real de Challonge con esta compilación. No se afirma que esta beta elimine el lag de menús reportado.
No incluye perfiles, credenciales, ISO ni memory. Se recomienda guardar una copia de la instalación anterior y reportar problemas con los registros locales.
