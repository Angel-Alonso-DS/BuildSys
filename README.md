# BuildSys backend MVP

The backend demonstrates learning transfer: a controlled duplicate-order observation creates a validated idempotency rule. A later returns system inherits that rule and stores one return for a repeated request.

## Run

```bash
./scripts/run-backend.sh
PYTHONPATH=apps/api/src python3 -m unittest discover -s apps/api/tests -v
```

## Demo

```bash
curl -X POST http://localhost:8000/learning/duplicate-event -H 'Content-Type: application/json' -d '{"source_system":"orders"}'
curl -X POST http://localhost:8000/systems/returns/build
curl -X POST http://localhost:8000/systems/returns/events -H 'Content-Type: application/json' -d '{"request_id":"return-100","payload":{"item":"book"}}'
curl -X POST http://localhost:8000/systems/returns/events -H 'Content-Type: application/json' -d '{"request_id":"return-100","payload":{"item":"book"}}'
curl http://localhost:8000/knowledge
```
