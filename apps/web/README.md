# BuildSys Learning Dashboard

Interfaz de demostración para aprender una regla de idempotencia en `orders` y transferirla a `returns`. Requiere Node.js 18 o posterior; no hay dependencias que instalar.

```bash
cd apps/web
npm start
# Abrir http://localhost:3000
```

La URL inicial de la API es `http://localhost:8000`. Para cambiarla al iniciar:

```bash
API_URL=http://192.168.1.20:8000 PORT=3000 npm start
```

También se puede configurar en la interfaz y pulsar **Conectar**. La URL se guarda como `API_URL` en `localStorage` del navegador y tiene prioridad sobre la variable de entorno. No incluyas credenciales ni secretos en la URL. La variable de entorno se publica al navegador y tampoco debe contener secretos.

El navegador debe poder acceder a la API y el backend debe permitir el origen exacto de la web mediante CORS. Con la rama del backend, por ejemplo, configura `BUILDSYS_ALLOWED_ORIGINS=http://localhost:3000` al iniciarlo; si se accede desde otro equipo, usa el origen que aparece en la barra del navegador. Para un frontend servido por HTTPS, la API también debe ser HTTPS para evitar el bloqueo de contenido mixto.

Conecta la API y sigue los cinco pasos en orden. Las respuestas reales aparecen en el panel de actividad; el conocimiento se consulta desde `GET /knowledge`. La misma carga `{ "request_id": "return-100", "payload": { "item": "book" } }` se envía en ambos intentos. Los datos persisten en el backend: para repetir la demostración completa con una primera respuesta `accepted`, inicia el backend con una base de datos nueva. La interfaz no borra eventos.

Comprobación de sintaxis:

```bash
npm run check
```
