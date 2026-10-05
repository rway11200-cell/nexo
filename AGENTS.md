# Nexo Budget API — instrucciones para agentes

## Rol del proyecto
Nexo es una API FastAPI que centraliza integraciones con Notion y Telegram para el presupuesto familiar, además de APIs de planificación y coding loop.

## Reglas de trabajo
- Responder en español cuando se interactúe con el equipo.
- No leer, imprimir, copiar ni modificar `.env`, secretos, tokens, claves SSH o credenciales.
- No hacer `git push`, cambiar remotos ni reescribir historial: Hermes coordina GitHub y Railway.
- No ejecutar Railway deploy desde OpenCode.
- Trabajar en una rama de tarea; no modificar `main` para experimentos.
- Antes de editar, leer las capas relacionadas: `routes.py`, `schemas.py`, `service.py`, `repository.py` y tests.
- Preferir tests con mocks; no llamar Notion, Telegram ni Railway desde tests.

## Validación
Usar un entorno aislado cuando sea necesario:

```bash
uv run --isolated --with-requirements requirements-dev.txt pytest -q -o addopts=''
```

La suite debe terminar sin efectos externos. Para cambios Python, validar también la sintaxis.

## Arquitectura
- `routes.py`: HTTP y autenticación.
- `schemas.py`: modelos Pydantic.
- `service.py`: lógica de negocio.
- `repository.py`: Notion/Telegram.
- `test_app.py`: regresión e integración HTTP mockeada.

## Flujo OpenCode/Hermes
1. OpenCode inspecciona, edita y prueba en su workspace.
2. OpenCode informa cambios y resultados; no publica.
3. Hermes revisa el diff, ejecuta validaciones adicionales y decide la integración.
4. Hermes es responsable de commit, push a GitHub y despliegue Railway, solo con autorización correspondiente.
