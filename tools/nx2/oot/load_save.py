import socket, json, time, re, sys, os
LOG = os.environ.get("LICHII_LOG", os.path.expanduser("~/.local/share/eden/log/eden_log.txt"))
def rpc(method, params, timeout=120):
    s = socket.create_connection(("127.0.0.1", 47890), timeout=timeout)
    s.sendall((json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}) + "\n").encode())
    data = b""
    while not data.endswith(b"\n"):
        chunk = s.recv(65536)
        if not chunk:
            break
        data += chunk
    s.close()
    return json.loads(data)
def in_game():
    last = None
    for line in open(LOG, errors="replace"):
        if "DKB cpu" in line:
            last = line
    return bool(last and (m := re.search(r"cpu_read_flushes=(\d+)", last)) and int(m.group(1)) > 0)
boot = time.monotonic()
while True:
    try:
        up = rpc("status", {})["result"]["uptime_s"]
    except OSError:
        up = 0
    if up >= 10:
        break
    if time.monotonic() - boot > 120:
        print("emulator not reachable after 120 s")
        sys.exit(1)
    time.sleep(3)
start = time.monotonic()
i = 0
while time.monotonic() - start < 90:
    i += 1
    r = rpc("input_sequence", {"steps": [{"buttons": ["A"], "frames": 6}, {"frames": 30}]})
    err = r.get("error")
    if err:
        print("press", i, err, flush=True)
    time.sleep(1)
    if in_game():
        print("in game after press", i, flush=True)
        sys.exit(0)
print("save not detected as loaded after", i, "presses")
sys.exit(1)
