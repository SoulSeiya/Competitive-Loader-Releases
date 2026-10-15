# Laboratorio online 0.1.35.2

Perfil experimental, solo por `local_online_test.py`. La GUI conserva el comportamiento anterior y NO activa este perfil.

La versión antigua permanece en la carpeta original. Esta copia no busca actualizaciones al ejecutar el laboratorio.
Se fija el SHA-256 del ejecutable Windows revisado; no basta con que coincidan sus símbolos.

Conserva 17 entradas de reglas/modelos/CPU competitivos y los datos de la ISO. Usa red, chat, pausa y voces lógicas oficiales. No carga competitive_chat.o: quedan fuera barreras, saltos de intros, audio ADX antiguo, marcador y bloqueo de ventana. Usa tiempos oficiales, pendientes de portar por separado. No convierte el vídeo de la intro.

La ISO 8.4.2 proporcionada localmente tiene las mismas firmas SLUS/DBZP aceptadas por el Loader; esto no demuestra por sí solo equivalencia de todos los datos ni fidelidad de cada regla competitiva.

## Preparación

Con Python 3 en Windows (el Python incluido en toolchain/msys64/ucrt64/bin también sirve):

```powershell
python local_online_test.py prepare --release RUTA_RELEASE --iso RUTA_ISO --card RUTA_PS2 --lab RUTA_NUEVA
python tools/make_online_script.py input-test.bin
python local_online_test.py run --lab RUTA_NUEVA --script input-test.bin --seconds 120
```

Cada prueba usa una carpeta nueva, con host y guest independientes. La preparación necesita espacio para dos copias completas. No usa el matchmaking público: conecta por UDP a 127.0.0.1. Ambos procesos se cierran al terminar el tiempo de prueba. Sin `--script` permite controles manuales.

Variaciones: `--rollback 0`, `--lag 60 --loss 10`, `--slow-start 3000` (invitado). El lag se aplica en cada lado.
Usa otra carpeta preparada para cada variación: no se sobrescriben registros.

## Evidencia

- manifest.json: hashes de ISO, memory, ejecutable y payload.
- host/ y guest/: game.log, worker.log, state-hashes.txt, competitive_loader.log.
- result.json: comparación y mensaje nativo de desync.
- analyze puede volver a leer los registros: `python local_online_test.py analyze --lab RUTA`.

El análisis conserva la última ejecución de cada blank por el rollback y compara vida, posiciones y reloj de combate. No trata como equivalentes los hashes del estado completo de dos vistas distintas. Una diferencia observada debe correlacionarse con las comprobaciones nativas de input confirmado: no demuestra por sí sola un fallo permanente. No haber llegado a combate da INCONCLUSIVE. Un tiempo limitado sin divergencias no certifica estabilidad. El cierre por timeout puede dejar sin volcar el final del archivo de hashes.

Faltan pruebas de transformación, clashes, revancha, sesiones repetidas y dos PC reales. Los objetos de reglas competitivas proceden de la versión anterior y requieren revisión contra las estructuras nuevas.

No publicar como versión estable ni crear una etiqueta de Release hasta validar los resultados.
