# Dragon Ball Z Budokai Tenkaichi — Competitive Edition

Repositorio de **Competitive Loader**, la aplicación de Universo Tenkaichi para instalar y ejecutar Competitive Edition sobre una publicación oficial de Tenkaichi3Decomp.

El proyecto no incluye la ISO ni archivos del juego. Cada usuario debe proporcionar su propia copia de Competitive Edition.

## Código y compilación

El código de la aplicación está en [`CompetitiveLoader`](CompetitiveLoader). En Windows, desde esa carpeta:

```powershell
.\build.ps1
```

El paquete final queda en:

```text
CompetitiveLoader\release\CompetitiveLoader-windows-x64.zip
```

## Publicar una actualización

1. Cambia `APP_VERSION` en `CompetitiveLoader/competitive_loader.py`.
2. Actualiza `CompetitiveLoader/assets/version_info.txt` con la misma versión.
3. Confirma y sube los cambios a `main`.
4. Crea y sube una etiqueta con el mismo número, por ejemplo:

```powershell
git tag v1.0.0
git push origin v1.0.0
```

GitHub Actions construirá la aplicación, creará la Release y adjuntará exactamente `CompetitiveLoader-windows-x64.zip`. Al abrirse, las instalaciones v1 o posteriores detectarán esa Release, la instalarán automáticamente y se reiniciarán. Las versiones 0.16 y 0.17 muestran un botón para realizar la migración inicial a v1.

## Créditos

- Recomp: **z3xox**
- Competitive Loader: **Rising**

