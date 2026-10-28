import os, re, subprocess, sys

DEV_PORTS = [8000, 8101]

def _ts(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=8)
    except Exception:
        return None

def _listeners_non_loopback():
    try:
        r = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, timeout=8)
        found = []
        for line in r.stdout.splitlines():
            if "LISTENING" not in line:
                continue
            parts = [p for p in re.split(r"\s+", line.strip()) if p]
            if len(parts) < 2:
                continue
            local = parts[1]
            # netstat format: Proto  Local Address  Foreign Address  State  PID
            m = re.match(r"^(?:(\d{1,3}(?:\.\d{1,3}){3})|([0-9a-fA-F:]+)):(\d+)$", local)
            if not m:
                continue
            ip = m.group(1) or m.group(2) or ""
            port = int(m.group(3))
            if port in DEV_PORTS and ip != "127.0.0.1" and ip != "::1":
                found.append((ip, port))
        if found:
            return found
    except Exception:
        pass
    return None

def _tunnel_running():
    try:
        ps = subprocess.run(["powershell", "-Command", 
            "Get-Process | Where-Object { $_.ProcessName -match 'cloudflared|ngrok|tailscale' } | "
            "Select-Object ProcessName, CommandLine"], 
            capture_output=True, text=True, timeout=8)
        out = ps.stdout or ""
        for line in out.splitlines():
            if "8000" in line or "8101" in line:
                return True
    except Exception:
        pass
    return False

def check():
    problems = []
    env = os.environ.get("ENVIRONMENT", "").strip().lower()
    if env != "development" and not os.environ.get("CI"):
        problems.append("ENVIRONMENT is not 'development'")
    nb = _listeners_non_loopback()
    if nb:
        problems.append("a process is LISTENING on %s (non-loopback)" % nb[0][0])
    f = _ts(["tailscale", "funnel", "status", "--json"])
    if f is not None and f.stdout and f.stdout.strip() not in ("{}",) and "No serve config" not in f.stdout:
        if f.stdout.strip():
            problems.append("tailscale funnel status is non-empty")
    s = _ts(["tailscale", "serve", "status", "--json"])
    if s is not None:
        out = s.stdout.strip()
        if out and out != "{}" and "No serve config" not in out:
            for p in DEV_PORTS:
                if str(p) in out:
                    problems.append("tailscale serve config targets port %d" % p)
    if _tunnel_running():
        problems.append("a tunnel agent (cloudflared/ngrok/tailscale) references a dev port")
    return problems

def main():
    problems = check()
    if problems:
        print("REFUSING dev bypass - one or more exposure conditions detected:")
        for p in problems:
            print(" - " + p)
        print("Inspect / fix, then re-run. This gate does not modify Tailscale or tunnels.")
        return 2
    print("dev safety: OK (loopback-only, ENVIRONMENT=development, no tunnel/funnel exposure of dev ports)")
    return 0

if __name__ == "__main__":
    sys.exit(main())