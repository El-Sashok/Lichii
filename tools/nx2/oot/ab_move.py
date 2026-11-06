import socket, json, sys, time, re, statistics, os

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

def log_seconds():
    out = []
    for line in open(LOG, errors="replace"):
        m = re.match(r"\[\s*([\d.]+)\].*DKB cpu (.*)", line)
        if m:
            out.append((float(m.group(1)), dict(re.findall(r"(\w+)=([-\d./]+)", m.group(2)))))
    return out

def pipelines(t0, t1):
    n, ms = 0, 0.0
    for line in open(LOG, errors="replace"):
        m = re.match(r"\[\s*([\d.]+)\].*ReportRuntimePipeline: \w+ pipeline built on the GPU thread in ([\d.]+) ms", line)
        if m and t0 <= float(m.group(1)) <= t1:
            n += 1
            ms += float(m.group(2))
    return n, ms

label = sys.argv[1] if len(sys.argv) > 1 else "run"
# 30 s: forward, camera sweep, strafe, back, forward again.
def run(stick, frames, cam=None, tap=None, every=84, hold=6):
    out = []
    done = 0
    while done < frames:
        n = min(every, frames - done)
        step = {"left_stick": stick, "frames": n}
        if cam:
            step["right_stick"] = cam
        out.append(step)
        done += n
        if tap and done < frames:
            m = min(hold, frames - done)
            pressed = {"left_stick": stick, "buttons": [tap], "frames": m}
            if cam:
                pressed["right_stick"] = cam
            out.append(pressed)
            done += m
    return out

# 30 s: forward with rolls (A), camera sweep, strafe with sword (B), back with rolls, forward.
steps = (run([0, 1], 300, tap="A") + run([0, 1], 240, cam=[1, 0], tap="A") +
         run([1, 0], 240, tap="B") + run([0, -1], 300, cam=[-1, 0], tap="A") +
         run([-1, 0], 240, tap="B") + run([0, 1], 300, cam=[0.6, 0], tap="A") +
         [{"frames": 180}])
assert sum(s["frames"] for s in steps) == 1800, sum(s["frames"] for s in steps)
before = log_seconds()
t_start = before[-1][0] if before else 0
status = rpc("status", {})["result"]
print(label, "status fps", round(status["fps"], 1), "uptime", round(status["uptime_s"], 1))
t0 = time.time()
result = rpc("input_sequence", {"steps": steps, "timeout_s": 120}, timeout=180)
print("input_sequence:", json.dumps(result.get("result", result))[:200], "wall", round(time.time() - t0, 1), "s")
time.sleep(1.5)
after = log_seconds()
window = [(t, d) for t, d in after if t > t_start]
frames = [int(d["frames"]) for t, d in window if "frames" in d]
back = [float(d["gpu_back_cpu_ms_per_frame"]) for t, d in window if "gpu_back_cpu_ms_per_frame" in d]
fin = [int(d.get("finishes", 0)) for t, d in window]
fin_ms = [float(d.get("finish_ms", 0)) for t, d in window]
waits = [int(d.get("read_waits", 0)) for t, d in window]
q = lambda v, p: sorted(v)[max(0, min(len(v) - 1, int(len(v) * p)))]
print(f"{label}: {len(frames)} s | fps min {min(frames)} p10 {q(frames, .1)} p25 {q(frames, .25)} med {q(frames, .5)} mean {statistics.mean(frames):.1f} | back ms med {q(back, .5):.1f} p90 {q(back, .9):.1f} max {max(back):.1f} | finishes/s {statistics.mean(fin):.0f} ({statistics.mean(fin_ms):.0f} ms/s) | read_waits/s {statistics.mean(waits):.0f}")
n, ms = pipelines(window[0][0], window[-1][0])
print(f"{label}: pipelines built {n} ({ms:.0f} ms)")
print("fps:", " ".join(str(f) for f in frames))
