# probe_tools.py -> pip install httpx -> python probe_tools.py MODEL_ID
import json, sys, httpx

BASE, MODEL = "http://localhost:13305/v1", sys.argv[1]
N = 10

TOOL = {"type": "function", "function": {
    "name": "check_placeholders",
    "description": "Compare placeholders between source and translation.",
    "parameters": {"type": "object",
                   "properties": {"source": {"type": "string"}, "mt": {"type": "string"}},
                   "required": ["source", "mt"]}}}

SOURCE = 'Hello {0}, {1} added you to team "{2}"'
MT = "Olá {0}, foi adicionado à equipe."
PLAIN = 'Source: ' + SOURCE + "\nTranslation: " + MT + "\nWhich checks are needed?"
NAMED = ('Call check_placeholders with source="%s" and mt="%s".'
         % (SOURCE.replace('"', '\\"'), MT))


def post(payload):
    r = httpx.post(f"{BASE}/chat/completions", json={"model": MODEL, **payload}, timeout=120)
    r.raise_for_status()
    return r.json()["choices"][0]


def sweep(label, content, expect_call):
    calls = good = selection = 0
    for i in range(N):
        try:
            msg = post({"messages": [{"role": "user", "content": content}],
                        "tools": [TOOL]})["message"]
        except Exception as e:
            print(f"[{label} {i}] request failed: {e}", flush=True)
            continue
        tc = msg.get("tool_calls")
        if not tc:
            print(f"[{label} {i}] no tool_calls: {str(msg.get('content'))[:70]!r}", flush=True)
            continue
        calls += 1
        fn = tc[0]["function"]
        if fn["name"] == "check_placeholders":
            selection += 1
        try:
            json.loads(fn["arguments"]); good += 1
        except Exception as e:
            print(f"[{label} {i}] bad args JSON: {e} raw={fn['arguments'][:100]!r}", flush=True)
    print(f"{label}: calls {calls}/{N} | right tool {selection}/{N} | valid args {good}/{N}",
          flush=True)
    return calls


named = sweep("named", NAMED, True)
auton = sweep("autonomous", PLAIN, True)

if auton:
    try:
        final = post({"messages": [
            {"role": "user", "content": PLAIN},
            {"role": "assistant", "content": None, "tool_calls": [{
                "id": "c1", "type": "function",
                "function": {"name": "check_placeholders",
                             "arguments": json.dumps({"source": SOURCE, "mt": MT})}}]},
            {"role": "tool", "tool_call_id": "c1",
             "content": json.dumps({"missing": ["{1}", "{2}"]})}],
            "tools": [TOOL]})
        print("round trip:", str(final["message"].get("content"))[:200], flush=True)
    except Exception as e:
        print("round trip FAILED:", e, flush=True)