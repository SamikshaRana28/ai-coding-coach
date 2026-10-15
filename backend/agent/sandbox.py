"""
User ka code apne main process mein KABHI exec nahi hota.
Alag subprocess mein chalta hai: timeout + memory limit + empty env.

NOTE: ye "good enough for a demo" sandbox hai. Production mein Docker
(--network none, --read-only, --memory 256m) ya gVisor/Firecracker use karo.
"""
import json
import os
import subprocess
import sys

TIMEOUT_SEC = 5
MEMORY_LIMIT_BYTES = 512 * 1024 * 1024
MAX_CODE_CHARS = 20_000

# Ye script subprocess ke andar chalti hai (stdin se JSON leti hai)
_RUNNER = r'''
import sys, json, io, contextlib

payload = json.loads(sys.stdin.read())
real_stdout = sys.stdout

def emit(obj):
    real_stdout.write("\n__RESULT__" + json.dumps(obj))
    real_stdout.flush()

ns = {"__name__": "candidate"}
sink = io.StringIO()
try:
    with contextlib.redirect_stdout(sink):
        exec(payload["code"], ns)
    fn = ns[payload["function"]]
except KeyError:
    emit({"error": "Function `%s` not found in your code." % payload["function"]}); sys.exit(0)
except BaseException as e:
    emit({"error": "%s: %s" % (type(e).__name__, e)}); sys.exit(0)

def same(got, expected, mode):
    if mode == "sorted" and isinstance(got, list) and isinstance(expected, list):
        try:
            return sorted(got) == sorted(expected)
        except TypeError:
            return False
    return got == expected

results = []
for t in payload["tests"]:
    args = json.loads(json.dumps(t["args"]))
    try:
        with contextlib.redirect_stdout(sink):
            got = fn(*args)
        ok = same(got, t["expected"], payload.get("compare", "exact"))
        results.append({"args": t["args"], "expected": t["expected"], "got": repr(got)[:200], "passed": ok})
    except BaseException as e:
        results.append({"args": t["args"], "expected": t["expected"], "got": "%s: %s" % (type(e).__name__, e), "passed": False})
emit({"results": results})
'''


def _limits():
    # Sirf Linux/Mac par chalta hai (Render/Codespaces dono Linux hain)
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT_BYTES, MEMORY_LIMIT_BYTES))
    resource.setrlimit(resource.RLIMIT_CPU, (TIMEOUT_SEC + 1, TIMEOUT_SEC + 1))


def run_code_against_tests(code: str, function: str, tests: list, compare: str = "exact") -> dict:
    if not code or not code.strip():
        return {"error": "No code provided."}
    if len(code) > MAX_CODE_CHARS:
        return {"error": "Code too long."}

    payload = json.dumps({"code": code, "function": function, "tests": tests, "compare": compare})
    try:
        proc = subprocess.run(
            [sys.executable, "-I", "-c", _RUNNER],
            input=payload, capture_output=True, text=True,
            timeout=TIMEOUT_SEC, env={},
            preexec_fn=_limits if os.name == "posix" else None,
        )
    except subprocess.TimeoutExpired:
        return {"error": f"Time limit exceeded ({TIMEOUT_SEC}s). Possible infinite loop or very slow solution."}

    marker = "\n__RESULT__"
    if marker not in proc.stdout:
        err = (proc.stderr or "Process crashed (possibly out of memory).").strip().splitlines()[-1:]
        return {"error": err[0] if err else "Process crashed."}

    data = json.loads(proc.stdout.split(marker, 1)[1])
    if "error" in data:
        return data

    results = data["results"]
    passed = sum(1 for r in results if r["passed"])
    failed = [r for r in results if not r["passed"]][:3]   # sirf pehle 3 failures dikhao
    return {"passed": passed, "total": len(results), "all_passed": passed == len(results), "failures": failed}
