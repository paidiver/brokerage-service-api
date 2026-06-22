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
