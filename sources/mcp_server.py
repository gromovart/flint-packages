"""Synthetic MCP stdio server: a constant result, no files or network."""
import json
import sys

for line in sys.stdin:
    request = json.loads(line)
    if "id" not in request:
        continue
    method = request.get("method")
    params = request.get("params", {})
    response = {"jsonrpc": "2.0", "id": request["id"]}
    if method == "initialize":
        response["result"] = {
            "protocolVersion": params.get("protocolVersion", "2025-03-26"),
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "flint-demo", "version": "1.0.0"}}
    elif method == "ping":
        response["result"] = {}
    elif method == "tools/list":
        response["result"] = {"tools": [{
            "name": "demo.ping", "description": "Return the fixed marker FLINT_DEMO_OK.",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}}]}
    elif method == "tools/call" and params.get("name") == "demo.ping" and params.get("arguments", {}) == {}:
        response["result"] = {"content": [{"type": "text", "text": "FLINT_DEMO_OK"}]}
    else:
        response["error"] = {"code": -32601, "message": "Unsupported method, tool or arguments"}
    print(json.dumps(response), flush=True)
