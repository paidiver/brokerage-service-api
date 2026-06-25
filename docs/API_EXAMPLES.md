# API Examples

Set your API base URL once:

```bash
export API_BASE="http://localhost:8020"
```

---

## Health endpoint

Check the health of the API:

```bash
curl -X GET "$API_BASE/health/" -H "accept: application/json"
```

Expected response:

```json
{"status": "ok"}
```

## Source Health Checks Endpoint

The brokerage service exposes an endpoint to check the live operational status of all configured upstream repository sources (e.g., BODC, JNCC). 

When this endpoint is hit, the application concurrently pings the `/health/` route of each enabled source defined in `source.yaml`. It aggregates their responses into a single payload, ensuring a single slow downstream dependency doesn't block the entire lifecycle.

### Endpoint Definition

* **Path:** `/api/sources/`
* **Method:** `GET`
* **Headers:** `Accept: application/json`

### Example Request

```bash
curl -X GET "http://localhost:8020/api/sources/" -H "accept: application/json"
```

```json
[
  {
    "source_name": "bodc",
    "source_label": "BRITISH OCEANOGRAPHIC DATA CENTRE",
    "base_url": "http://bodc-source:80",
    "status": "ok"
  },
  {
    "source_name": "jncc",
    "source_label": "JOINT NATURE CONSERVATION COMMITTEE",
    "base_url": "http://jncc-source:80",
    "status": "unhealthy",
    "error": "Upstream returned 502: Bad Gateway"
  }
]
```

## Accessing & Utilizing Source Configuration

If you are developing a new endpoint or service within the brokerage application and need to forward requests to a specific upstream source, you can access the verified configuration directly from the FastAPI application state.

### Retrieving a Source from Application State

We can access the global state dictionary via the incoming `Request` object. This ensures you do not have to waste performance re-reading the `source.yaml` file from disk during an active request lifecycle.

```python
from fastapi import APIRouter, Request, HTTPException
import httpx

router = APIRouter()

@router.get("/api/data/{source_id}")
async def fetch_upstream_data(source_id: str, request: Request):
    # 1. Access the immutable global registry from state
    sources_config = request.app.state.sources
    
    # 2. Look up the specific source (e.g., 'bodc' or 'jncc')
    source = sources_config.get(source_id)
    if not source or not source.enabled:
        raise HTTPException(status_code=404, detail=f"Source '{source_id}' not found or is disabled.")
        
    # The 'source' object is an instance of your validated SourceConfig model
    return {"message": f"Successfully retrieved configuration for {source.label}"}
```
