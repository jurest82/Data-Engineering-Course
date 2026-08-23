# CLAUDE.md: Data Engineering Course

## Qué es este proyecto

Pipeline de datos batch que ingiere reportes de accidentes de tránsito, cargados como un archivo Excel, para el servicio de monitoreo de tráfico descrito en `README.md`. Este documento cubre el flujo **batch** y el flujo de **streaming** de sensores de tráfico (ambos completos, ver sus propias secciones).

## Cómo trabajar en este repositorio

No se instala nada de este proyecto directamente en el host. Todo el trabajo de `backend` e `infrastructure` (instalar dependencias, correr `aws` CLI, `serverless` CLI, formatear/lintear Python, desplegar) se hace levantando el contenedor Docker correspondiente (`docker compose`, usando el `.docker/docker-compose.yml` de ese subproyecto) y ejecutando ahí dentro, replicando lo que hace su `entrypoint.sh` (configuración de git, `npm install`, credenciales AWS desde `.envs/`).

## Estructura del monorepo

- **Raíz**: devcontainer liviano (solo Node), para trabajo a nivel de monorepo. `.docker/Dockerfile` es multi-stage: `img-base` (Python 3.13 + Node 24 + herramientas comunes, incluye `~/.cfnlintrc` para que `cfn-lint` ignore el falso positivo W3005 que agrega Serverless Framework) → `img-backend` (suma `boto3`, solo para que el linter/autocompletado local resuelva los imports; el runtime de Lambda ya lo trae, nunca se empaqueta) / `img-infrastructure` (sin diferencias adicionales por ahora).
- **`backend/`**: contiene **varios stacks de Serverless Framework, cada uno en su propia carpeta bajo `backend/serverless/<stack>/`** (mismo patrón que `infrastructure/serverless/<stack>/`), no un solo stack para todo el backend:
  - `backend/serverless/layers` (`service: backend-layers`): solo las Lambda Layers compartidas, sin funciones propias. **Debe desplegarse primero**, ya que los demás stacks de `backend` consumen sus ARNs vía SSM.
  - `backend/serverless/batch` (`service: backend-batch`): API Gateway + las 3 Lambdas del flujo batch + sus roles IAM.
  - Código de las Lambdas en `backend/src/<nombre_funcion>/`, en **Python**, formateado con `yapf` + `isort` (ver `pyproject.toml`); lógica compartida entre Lambdas en `backend/src/common/`. Como cada `serverless.yml` vive dos niveles bajo `backend/` (`backend/serverless/<stack>/`), el `package.patterns` de cada función referencia su código con `../../src/...`.
  - **Dependencias de Python van por Lambda Layers, no por `requirements.txt` empaquetado en cada función.** Cada capa vive en `backend/src/layers/<nombre>/` (con su propio `requirements.txt` y `.gitignore` que ignora la carpeta `python/` generada) y se define en `backend/serverless/layers/layers.yml` con `path: ../../src/layers/<nombre>` + `package.patterns: ['!./**', 'python/**']`. Como las capas viven en un stack separado, las funciones de los demás stacks de `backend` las referencian por ARN vía SSM (`layers: [${ssm:/${env:DEPLOY_APP}-backend-layers/<Nombre>LayerArn}]`), no con `!Ref` directo. El `entrypoint.sh` de `backend` instala esas dependencias en `src/layers/<nombre>/python/` y genera un `.pth` en el contenedor para que también funcionen en pruebas locales.
  - **Por qué no `module:`**: la opción `module` de la integración de Python requirements (para requirements.txt por función) cambia la raíz efectiva del zip a la carpeta de la función, lo cual choca con `package.patterns` (que sigue resolviendo rutas relativas a donde vive `serverless.yml`) y con tener código compartido (`common/`) fuera de esa carpeta; con esa combinación el empaquetado queda inconsistente y no incluye ningún archivo. Las Lambda Layers evitan el problema por completo (tienen su propio mecanismo de `path:` para la raíz).
  - **Capas actuales**: `Commons` (`openpyxl`), `Mongo` (`pymongo`), `Security` (`cryptography`). Cada Lambda solo referencia las capas que realmente necesita (ej. Lambda 1/2 no cargan `Mongo` ni `Security`).
  - **Secretos referenciados por nombre, no por ARN**: `custom.secretsManager.<nombre>` construye directo el nombre del secreto (ej. `/${env:DEPLOY_APP}-secrets/MongoCredentials`, coincide con cómo lo nombra `infrastructure`), sin buscar el ARN por SSM. El IAM sí necesita un ARN, así que se arma con un wildcard: `arn:aws:secretsmanager:${AWS::Region}:${AWS::AccountId}:secret:<nombre>-*` (el `-*` cubre el sufijo aleatorio que Secrets Manager agrega).
  - **Arquitectura de despliegue (`x86_64`/`arm64`) se resuelve dinámicamente**, no a mano: `provider.architecture: ${file(../architecture.js):get}` (un solo `architecture.js` compartido en `backend/serverless/`, referenciado por los 3 stacks), un script que devuelve `process.arch` de Node. Necesario porque `pymongo`/`cryptography` traen extensiones compiladas, y deben coincidir con la arquitectura de quien despliegue (relevante porque los estudiantes pueden tener Mac Apple Silicon o Intel/Windows x86).
  - **Casos de prueba**: `backend/tests/fixtures/batch/` tiene Excels de ejemplo (`valid_report.xlsx`, `missing_column.xlsx`, `invalid_rows.xlsx`, `exceeds_max_rows.xlsx`) y `generate_base64.sh`, que genera un `.json` por cada `.xlsx` con el body listo para pegar en Postman (`{"file": "<base64>"}`). `backend/tests/fixtures/sensor_readings/` tiene payloads MQTT de ejemplo para pegar en el MQTT test client de la consola de IoT Core (ver su propio `README.md`).
- **`infrastructure/`**: recursos base compartidos (Serverless Framework): S3, SQS+DLQ, Secrets Manager, y alarmas de CloudWatch. No despliega los roles IAM de las Lambdas, eso es responsabilidad de `backend`. Cada recurso vive en su propio sub-stack (`serverless/storage`, `serverless/queue`, `serverless/secrets`, `serverless/alerts`), desplegado de forma independiente. `serverless/queue` es deliberadamente de propósito general, no exclusivo del batch: alberga tanto `AccidentReports`/su DLQ (batch) como `SensorReadings`/su DLQ (streaming), en vez de tener un sub-stack de colas por flujo. Todos son independientes entre sí **excepto `alerts`**, que debe desplegarse **después** de `backend/serverless/batch` (sus alarmas referencian, vía SSM, el nombre de la Lambda `SplitAndEnqueue` que exporta ese stack) — es la única inversión del orden habitual infra-antes-que-backend.
- **`frontend/`** y **`etl/`**: mencionados en `README.md` como parte del monorepo, pero no existen todavía. Mientras no exista frontend, el flujo batch se prueba directo contra el API (ej. con Postman).
- Cada subproyecto (`backend`, `infrastructure`) tiene su propio devcontainer, `docker-compose.yml`, `entrypoint.sh`, `.envs/config.env` (con `DEVELOPER`, usado para que los nombres de recursos desplegados no choquen entre desarrolladores) y `ws.code-workspace` (workspace multi-root que también deja visibles los `.envs` del otro subproyecto y los compartidos de la raíz).

## Infraestructura como código

Serverless Framework, solo CLI, sin Serverless Dashboard: no se ponen las keys `org:` ni `app:` al inicio de ningún `serverless.yml`. `SERVERLESS_ACCESS_KEY` (en `.envs/sls.env`) es solo para licenciamiento del CLI.

- Plugin `@serverless/safeguards-plugin`: reglas definidas **localmente** en la sección `custom.safeguards` de cada `serverless.yml` (ej. `allowed-regions`, `allowed-function-names`, `no-wild-iam-role-statements`, `allowed-stages`), no reglas remotas de Dashboard.
- Plugin `serverless-deployment-bucket`: bucket de despliegue propio por stack, con naming que incluye `DEVELOPER` en `dev` para evitar colisiones entre desarrolladores.
- Linting de las plantillas CloudFormation generadas: `cfn-lint` + `cfn-lint-serverless`.

## Arquitectura del flujo batch

Cliente envía un `POST` a API Gateway con el Excel de accidentes codificado en **base64**, máximo **300 filas** por archivo.

**Estado: los 3 pasos (Lambda 1, 2 y 3) están construidos, desplegados y probados.**

1. **Lambda 1** (`ValidateAndStore`, invocada por API Gateway, síncrona) — ✅ construida: valida la estructura del Excel **y** las reglas de negocio; si cualquier fila es inválida, rechaza el archivo completo (no guarda nada, responde 400 con el detalle). Si todo es válido, guarda el archivo crudo en S3 y responde rápido, sin esperar el resto del procesamiento (evita el límite de 29s de API Gateway). Esquema del Excel (columnas en español, mapeadas a inglés para el código/Mongo):

   | Columna Excel | Campo en código/Mongo | Validación |
   |---|---|---|
   | `fecha` + `hora` | `occurred_at` | Se combinan en un solo timestamp ISO 8601 |
   | `ciudad` | `city` | Bogotá, Medellín, Cali o Barranquilla |
   | `via` | `road` | Texto no vacío |
   | `severidad` | `severity` | leve/moderado/grave/fatal en el Excel, traducido a minor/moderate/severe/fatal al guardar |
   | `vehiculos_involucrados` | `vehicles_involved` | Entero 1-20 |
   | `nombre_persona_involucrada` | `involved_person_name` | Texto no vacío (PII) |
   | `cedula_persona_involucrada` | `involved_person_id` | Numérico, 6-10 dígitos (PII) |

   API expuesta como REST API (no HTTP API) para poder usar el API Key nativo de API Gateway (`private: true` en el evento + `provider.apiGateway.apiKeys`): sin el header `x-api-key` correcto, API Gateway rechaza la petición antes de invocar la Lambda. Esquema y validaciones compartidos en `backend/src/common/accident_reports.py`, reusado por las Lambdas 2 y 3. `severity` además se traduce (leve→minor, moderado→moderate, grave→severe, fatal→fatal) antes de guardarse; `city`/`road` no se traducen (nombres propios).
2. El evento `ObjectCreated` de ese bucket S3 dispara **Lambda 2** (`SplitAndEnqueue`) — ✅ construida: reusa `backend/src/common/accident_reports.py` para volver a parsear/validar el Excel (Lambda 1 no le pasa los datos ya parseados, solo el archivo en S3) y, si todo sigue siendo válido, fracciona el Excel en un JSON por fila (con `source_s3_key` y `row_number` para trazabilidad) y los envía a SQS con `send_message_batch` (lotes de hasta 10). Al terminar, mueve el archivo (copia + borra, S3 no tiene "mover" nativo) a `processed/` si salió bien o a `failed/` si algo falló (antes de re-lanzar el error). El trigger de S3 está acotado al prefijo `uploads/` (`rules: - prefix: uploads/`), indispensable para no disparar un bucle al mover archivos hacia `processed/`/`failed/` dentro del mismo bucket. Que Lambda 2 falle revalidando un archivo que Lambda 1 ya aceptó es síntoma de un bug propio (no de datos del usuario, ese caso ya lo resolvió Lambda 1 de forma síncrona); por eso alertar de esos fallos es un tema operativo (ver alarma de CloudWatch diferida más abajo), no algo que el usuario necesite ver.
3. **SQS**, con una **Dead Letter Queue (DLQ)** configurada, dispara **Lambda 3** (`ValidateAndPersist`) — ✅ construida, con tamaño de lote 1 (procesa una fila por invocación):
   - Valida la fila (defensa en profundidad; no confiar ciegamente en lo que ya validó Lambda 1/2).
   - Si es válida: cifra `involved_person_name` e `involved_person_id` (Fernet, llave desde Secrets Manager) antes de guardar; obtiene las credenciales de Mongo desde **Secrets Manager** (cacheadas en una variable de módulo entre invocaciones "warm") y usa un **cliente de Mongo también cacheado/reutilizado** entre invocaciones, para guardar el documento (con `created_at`/`updated_at` en UTC) en MongoDB Atlas.
   - Si falla la validación: la Lambda **envía explícitamente el mensaje a la DLQ ella misma** (fila original + `validation_errors`), en vez de dejar que la excepción se propague y que SQS la reintente varias veces hasta agotar su `maxReceiveCount` (una fila con datos inválidos no se arregla reintentando; la DLQ debe reservarse conceptualmente para fallas de procesamiento, no solo para "SQS se rindió"). El PII en ese mensaje de la DLQ queda en texto plano a propósito, para que alguien pueda corregir el dato antes de un redrive.
   - Concurrencia reservada: **no aplicada, de forma permanente mientras este proyecto se construya sobre una cuenta de AWS free tier** (límite total de solo 10 ejecuciones concurrentes, con al menos 10 sin reservar exigido por AWS); no hay margen para reservar nada.
4. Roles IAM: uno por Lambda, con permisos mínimos (Lambda 1: `s3:PutObject`; Lambda 2: `s3:GetObject`/`DeleteObject` en `uploads/*`, `s3:PutObject` en `processed/*` y `failed/*`, `sqs:SendMessage`; Lambda 3: `sqs:ReceiveMessage`/`DeleteMessage` en la cola, `sqs:SendMessage` a la DLQ, `secretsmanager:GetSecretValue` acotado a los ARNs de los secretos de Mongo y de la llave PII).

**Base de datos**: MongoDB Atlas, tier gratuito **M0** (no AWS DocumentDB: no tiene free tier real y exigiría poner las Lambdas dentro de una VPC).

`backend` expone el API con la URL por defecto de API Gateway, sin dominio personalizado.

## Arquitectura del flujo streaming

Sensores fijos de tráfico reportan velocidad promedio y conteo de vehículos por vía, cada pocos segundos, vía MQTT contra **AWS IoT Core**. Mismo patrón ya probado en el flujo batch: **IoT Core → SQS → Lambda → MongoDB**, con la Lambda validando de nuevo por defensa en profundidad y reenviando ella misma las filas inválidas a su propia DLQ (mismo criterio que Lambda 3 del batch).

**Por qué no Kinesis Data Streams**: es el servicio de streaming "clásico" de AWS, pero no tiene free tier real (cobra por shard-hora desde el minuto uno, sin importar el tráfico) — rompería la premisa de este proyecto de vivir en free tier. IoT Core sí tiene free tier de mensajes, y además encaja temáticamente con "sensores".

**Estado**: construido, desplegado y probado de punta a punta, tanto con `aws iot-data publish` como con certificado real vía `mosquitto_pub` (ver más abajo).
- Las 3 Lambda Layers compartidas viven en su propio stack (`backend/serverless/layers`, ver "Estructura del monorepo"), consumidas también por este flujo.
- Colas `SensorReadings`/`SensorReadingsDLQ` en `infrastructure/serverless/queue` (mismo stack que ya alojaba las colas del batch) — ✅ desplegadas.
- Stack `infrastructure/serverless/iot` — ✅ desplegado: una **Policy de IoT genérica y reusable** (no ligada a un dispositivo específico) que usa variables de política de IoT (`${iot:Connection.Thing.ThingName}`) para que cada certificado solo pueda conectarse/publicar en su propio tópico (`sensors/traffic/<su-thing-name>/data`), y un `AWS::IoT::TopicRule` (`SELECT * FROM 'sensors/traffic/+/data'`) que enruta cada mensaje a `SensorReadingsQueue`, con su propio rol IAM (`sqs:SendMessage` acotado a esa cola). Deliberadamente **no** incluye el Thing/certificado de un dispositivo concreto — eso es aprovisionamiento por sensor, no un recurso fijo del stack (ver `provision_sensor.sh` más abajo).
- Stack `backend/serverless/streaming` — ✅ desplegado: Lambda `PersistSensorReading` (batchSize 1, mismo patrón de defensa en profundidad + auto-envío a su DLQ que Lambda 3 del batch) + su rol IAM. Esquema de la lectura: `sensor_id`, `city`, `road`, `speed_avg`, `vehicle_count`, `recorded_at` — sin PII (no hay persona involucrada), así que no usa cifrado ni la capa `Security`. Persiste en MongoDB Atlas, misma base `trafficMonitoring`, colección nueva `trafficSensorReadings`.
- `backend/src/common/mongo.py`: helper compartido de conexión/caché a Mongo (`get_collection(secret_name, collection_name)`), extraído para que tanto `PersistSensorReading` como Lambda 3 del batch lo reusen sin duplicar el patrón de caché de cliente "warm".
- Alarma de CloudWatch sobre la DLQ de lecturas de sensores, en el mismo stack `alerts` del batch (ver "Observabilidad").
- Probado de punta a punta con `aws iot-data publish` (publica directo con credenciales de IAM, sin certificado de dispositivo — válido para probar el mecanismo IoT Core → cola → Lambda, pero no la autenticación real de un sensor).
- Simulación de sensores con certificado real: `backend/tests/sensor_readings/provision_sensor.sh <sensor-id>` (crea el Thing + certificado X.509, le adjunta la `SensorReadingsPolicy` ya desplegada y el Thing; idempotente por sensor) y `send_sensor_reading.sh <sensor-id> [archivo] [tópico]` (publica vía `mosquitto_pub` con mTLS, el mismo camino de autenticación que usaría un sensor real). Probado con éxito: publicación válida y publicación inválida (a su propia DLQ) con `sensor-001`, y la prueba negativa — el certificado de `sensor-002` publicando en el tópico de `sensor-001` — confirmada bloqueada por la Policy (verificado suscribiéndose a ese tópico desde la consola de IoT Core: el mensaje nunca llegó). `mosquitto_pub`'s `-i` debe coincidir con el nombre del Thing del certificado, ya que la Policy usa `${iot:Connection.Thing.ThingName}` para el `iot:Connect`; un client ID distinto corta la conexión de inmediato ("connection was lost"). Requiere el paquete `mosquitto-clients` (ya en `img-backend`).

## Observabilidad

Stack `infrastructure/serverless/alerts` — ✅ construido: un tópico de SNS con una suscripción por email (`ALERTS_EMAIL`, requiere confirmar la suscripción la primera vez que se despliega) recibe tres alarmas de CloudWatch:

- Mensajes visibles en la DLQ de accidentes (`ApproximateNumberOfMessagesVisible >= 1`): indica filas que Lambda 3 no pudo validar/procesar.
- Errores en Lambda 2 (`SplitAndEnqueue`, métrica `Errors` >= 1): indica que falló revalidando un archivo que Lambda 1 ya había aceptado, síntoma de un bug propio (ver punto 2 de la arquitectura del flujo batch).
- Mensajes visibles en la DLQ de lecturas de sensores (`ApproximateNumberOfMessagesVisible >= 1`, mismo criterio que la de accidentes): indica lecturas que `PersistSensorReading` no pudo validar/procesar.

No hay alarma sobre errores de Lambda 1 ni de Lambda 3: Lambda 1 responde sus errores directo al cliente vía API Gateway (síncrono), y las filas inválidas de Lambda 3 van a la DLQ (ya cubierta por la alarma de arriba) en vez de lanzar una excepción. Streaming no tiene un paso equivalente a Lambda 2 (IoT Core enruta directo a la cola sin re-validación intermedia), así que tampoco tiene esa segunda alarma de "bug propio".

El mismo stack define también un **AWS Budget de costo** (`AWS::Budgets::Budget`, USD 1/mes, notifica por email tanto por gasto real como proyectado): a diferencia de las alarmas de CloudWatch (acotadas a este pipeline), el Budget cubre el gasto de **toda la cuenta de AWS**, pensado para detectar cuando algo se salió del free tier. Deliberadamente no se activó también "Free Tier Alerts" (una preferencia de cuenta en Billing, no un recurso de IaC, que avisaría antes de generar cualquier cargo real): se consideró y se descartó por redundante frente al Budget para el alcance de este proyecto.

## Convención de commits

Base: Conventional Commits (ver [artículo de referencia](https://medium.com/@iambonitheuri/the-art-of-writing-meaningful-git-commit-messages-a56887a4cb49)): tipos como `feat`/`fix`/`refactor`/`chore`/`docs`/`test`/etc., modo imperativo, sin punto final.

**Estilo real que usa Juan Pablo en este repo**: cada línea del mensaje es un bullet `* <type>: <descripción>` (con el `*` literal al inicio), una línea por cada cambio distinto, aunque varios queden en el mismo commit. Sin cuerpo aparte, sin explicación adicional debajo de los bullets. Ejemplo real:
```
* feat: add ValidateAndStore Lambda behind a REST API with an API key
* feat: add shared Commons Lambda layer for Python dependencies
* chore: ignore Lambda layer python/ folders in prettier, yapf and isort
* docs: update backend README deployment section for the single-stack layout
```
Cuando un commit toca varias cosas (código + docs, por ejemplo), reflejar cada una en su propio bullet, no resumir solo la principal. Si los cambios son de naturaleza muy distinta, preferir varios commits separados en vez de un solo commit con muchos bullets no relacionados.

**Nunca agregar co-autoría de Claude en los commits de este repositorio.**

## Pendientes abiertos

- Frontend para subir el Excel: no es parte del alcance actual.
