# CLAUDE.md: Data Engineering Course

## Qué es este proyecto

Pipeline de datos batch que ingiere reportes de accidentes de tránsito, cargados como un archivo Excel, para el servicio de monitoreo de tráfico descrito en `README.md`. Este documento cubre el flujo **batch**; el flujo de streaming (sensores de tráfico) es un stack independiente que se documenta aparte cuando exista.

## Cómo trabajar en este repositorio

No se instala nada de este proyecto directamente en el host. Todo el trabajo de `backend` e `infrastructure` (instalar dependencias, correr `aws` CLI, `serverless` CLI, formatear/lintear Python, desplegar) se hace levantando el contenedor Docker correspondiente (`docker compose`, usando el `.docker/docker-compose.yml` de ese subproyecto) y ejecutando ahí dentro, replicando lo que hace su `entrypoint.sh` (configuración de git, `npm install`, credenciales AWS desde `.envs/`).

## Estructura del monorepo

- **Raíz**: devcontainer liviano (solo Node), para trabajo a nivel de monorepo. `.docker/Dockerfile` es multi-stage: `img-base` (Python 3.13 + Node 24 + herramientas comunes) → `img-backend` / `img-infrastructure`.
- **`backend/`**: API Gateway + Lambdas + sus roles IAM (Serverless Framework), en `backend/serverless/` (`serverless.yml`, `functions.yml`, `iam.yml`, `layers.yml`; un solo stack para todo el backend). Código de las Lambdas en `backend/src/<nombre_funcion>/`, en **Python**, formateado con `yapf` + `isort` (ver `pyproject.toml`); lógica compartida entre Lambdas en `backend/src/common/`. Como `serverless.yml` vive en `backend/serverless/` (no en `backend/`), el `package.patterns` de cada función referencia su código con `../src/...` (glob `**` o archivos individuales, ambos funcionan bien).
  - **Dependencias de Python van por Lambda Layers, no por `requirements.txt` empaquetado en cada función.** Cada capa vive en `backend/src/layers/<nombre>/` (con su propio `requirements.txt` y `.gitignore` que ignora la carpeta `python/` generada) y se define en `layers.yml` con `path: ../src/layers/<nombre>` + `package.patterns: ['!./**', 'python/**']`; las funciones la referencian con `layers: [!Ref <Nombre>LambdaLayer]`. El `entrypoint.sh` de `backend` instala esas dependencias en `src/layers/<nombre>/python/` y genera un `.pth` en el contenedor para que también funcionen en pruebas locales.
  - **Por qué no `module:`**: la opción `module` de la integración de Python requirements (para requirements.txt por función) cambia la raíz efectiva del zip a la carpeta de la función, lo cual choca con `package.patterns` (que sigue resolviendo rutas relativas a donde vive `serverless.yml`) y con tener código compartido (`common/`) fuera de esa carpeta; con esa combinación el empaquetado queda inconsistente y no incluye ningún archivo. Las Lambda Layers evitan el problema por completo (tienen su propio mecanismo de `path:` para la raíz).
  - **Casos de prueba**: `backend/tests/fixtures/` tiene Excels de ejemplo (`valid_report.xlsx`, `missing_column.xlsx`, `invalid_rows.xlsx`, `exceeds_max_rows.xlsx`) y `generate_base64.sh`, que genera un `.json` por cada `.xlsx` con el body listo para pegar en Postman (`{"file": "<base64>"}`).
- **`infrastructure/`**: recursos base compartidos (Serverless Framework): S3, SQS+DLQ, Secrets Manager. No despliega los roles IAM de las Lambdas, eso es responsabilidad de `backend`.
- **`frontend/`** y **`etl/`**: mencionados en `README.md` como parte del monorepo, pero no existen todavía. Mientras no exista frontend, el flujo batch se prueba directo contra el API (ej. con Postman).
- Cada subproyecto (`backend`, `infrastructure`) tiene su propio devcontainer, `docker-compose.yml`, `entrypoint.sh`, `.envs/config.env` (con `DEVELOPER`, usado para que los nombres de recursos desplegados no choquen entre desarrolladores) y `ws.code-workspace` (workspace multi-root que también deja visibles los `.envs` del otro subproyecto y los compartidos de la raíz).

## Infraestructura como código

Serverless Framework, solo CLI, sin Serverless Dashboard: no se ponen las keys `org:` ni `app:` al inicio de ningún `serverless.yml`. `SERVERLESS_ACCESS_KEY` (en `.envs/sls.env`) es solo para licenciamiento del CLI.

- Plugin `@serverless/safeguards-plugin`: reglas definidas **localmente** en la sección `custom.safeguards` de cada `serverless.yml` (ej. `allowed-regions`, `allowed-function-names`, `no-wild-iam-role-statements`, `allowed-stages`), no reglas remotas de Dashboard.
- Plugin `serverless-deployment-bucket`: bucket de despliegue propio por stack, con naming que incluye `DEVELOPER` en `dev` para evitar colisiones entre desarrolladores.
- Linting de las plantillas CloudFormation generadas: `cfn-lint` + `cfn-lint-serverless`.

## Arquitectura del flujo batch

Cliente envía un `POST` a API Gateway con el Excel de accidentes codificado en **base64**, máximo **300 filas** por archivo.

1. **Lambda 1** (`ValidateAndStore`, invocada por API Gateway, síncrona): valida la estructura del Excel **y** las reglas de negocio; si cualquier fila es inválida, rechaza el archivo completo (no guarda nada, responde 400 con el detalle). Si todo es válido, guarda el archivo crudo en S3 y responde rápido, sin esperar el resto del procesamiento (evita el límite de 29s de API Gateway). Esquema del Excel (columnas en español, mapeadas a inglés para el código/Mongo):

   | Columna Excel | Campo en código/Mongo | Validación |
   |---|---|---|
   | `fecha` + `hora` | `occurred_at` | Se combinan en un solo timestamp ISO 8601 |
   | `ciudad` | `city` | Bogotá, Medellín, Cali o Barranquilla |
   | `via` | `road` | Texto no vacío |
   | `severidad` | `severity` | leve, moderado, grave o fatal |
   | `vehiculos_involucrados` | `vehicles_involved` | Entero 1-20 |
   | `nombre_persona_involucrada` | `involved_person_name` | Texto no vacío (PII) |
   | `cedula_persona_involucrada` | `involved_person_id` | Numérico, 6-10 dígitos (PII) |

   API expuesta como REST API (no HTTP API) para poder usar el API Key nativo de API Gateway (`private: true` en el evento + `provider.apiGateway.apiKeys`): sin el header `x-api-key` correcto, API Gateway rechaza la petición antes de invocar la Lambda. Esquema y validaciones compartidos en `backend/src/common/accident_reports.py`, reusado por las Lambdas 2 y 3 cuando existan.
2. El evento `ObjectCreated` de ese bucket S3 dispara **Lambda 2**: fracciona el Excel en un JSON por fila y los envía a SQS usando `send_message_batch` (lotes de hasta 10), no uno por uno.
3. **SQS**, con una **Dead Letter Queue (DLQ)** configurada, dispara **Lambda 3** con tamaño de lote 1 (procesa una fila por invocación):
   - Valida la fila (defensa en profundidad; no confiar ciegamente en lo que ya validó Lambda 1).
   - Si es válida: obtiene las credenciales de Mongo desde **Secrets Manager** (cacheadas en una variable de módulo entre invocaciones "warm") y usa un **cliente de Mongo también cacheado/reutilizado** entre invocaciones, para guardar el documento en MongoDB Atlas.
   - Si falla la validación: la Lambda **envía explícitamente el mensaje a la DLQ ella misma**, en vez de dejar que la excepción se propague y que SQS la reintente varias veces hasta agotar su `maxReceiveCount` (una fila con datos inválidos no se arregla reintentando; la DLQ debe reservarse conceptualmente para fallas de procesamiento, no solo para "SQS se rindió").
   - Concurrencia reservada baja (ej. 5) en Lambda 3, para no saturar el cluster M0 (gratuito) de MongoDB Atlas con demasiadas conexiones concurrentes.
4. Roles IAM: uno por Lambda, con permisos mínimos (Lambda 1: `s3:PutObject`; Lambda 2: `s3:GetObject` + `sqs:SendMessage`; Lambda 3: `sqs:ReceiveMessage`/`DeleteMessage` + `secretsmanager:GetSecretValue` acotado al ARN del secreto).

**Base de datos**: MongoDB Atlas, tier gratuito **M0** (no AWS DocumentDB: no tiene free tier real y exigiría poner las Lambdas dentro de una VPC).

`backend` expone el API con la URL por defecto de API Gateway, sin dominio personalizado.

## Gobernanza y observabilidad diferidas

Documentado en `changelog.md`, bajo `## [Unreleased]`:

- Manejo de PII (`nombre_persona_involucrada`, `cedula_persona_involucrada`): decidir si se enmascara, tokeniza o cifra a nivel de campo antes de guardar en Mongo (Ley 1581 de 2012, Colombia).
- Alarma de CloudWatch sobre la DLQ (hoy no hay ninguna alerta configurada cuando algo cae ahí).

## Convención de commits

Estilo Conventional Commits (ver [artículo de referencia](https://medium.com/@iambonitheuri/the-art-of-writing-meaningful-git-commit-messages-a56887a4cb49)): `<type>[scope]: <descripción>`, tipos como `feat`/`fix`/`refactor`/`chore`/`docs`/etc., asunto en modo imperativo, máximo 50 caracteres, primera letra en mayúscula, sin punto final; cuerpo opcional envuelto a 72 caracteres explicando qué y por qué.

**Nunca agregar co-autoría de Claude en los commits de este repositorio.**

## Pendientes abiertos

- Frontend para subir el Excel: no es parte del alcance actual.
- Diferenciar de verdad las imágenes Docker `img-backend` / `img-infrastructure` en `.docker/Dockerfile` si en algún momento necesitan dependencias distintas (hoy son idénticas).
