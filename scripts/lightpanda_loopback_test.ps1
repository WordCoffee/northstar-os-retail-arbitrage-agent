# Lightpanda loopback isolation test (owner-required proof).
#
# Proves the CDP port is NOT reachable from other devices:
#   1. The host-side listener must be bound to 127.0.0.1 ONLY (binding proof).
#   2. A connection attempt to this machine's LAN IP on port 9222 must FAIL —
#      that is the exact destination another device would use.
#   3. Positive control: CDP must answer on 127.0.0.1:9222.
#
# Usage: powershell -NoProfile -File scripts/lightpanda_loopback_test.ps1
# Exit 0 = PASS, 1 = FAIL.
$ErrorActionPreference = "Stop"
$Port = 9222
$fails = 0

Write-Host "== Lightpanda loopback isolation test (port $Port) =="

# 1. Binding proof — the socket must exist ONLY on loopback addresses.
$listeners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if (-not $listeners) {
    Write-Host "FAIL: nothing is listening on port $Port (is the container up?)"
    exit 1
}
$addresses = @($listeners | Select-Object -ExpandProperty LocalAddress -Unique)
Write-Host ("listeners: " + ($addresses -join ", "))
if (($addresses -contains "0.0.0.0") -or ($addresses -contains "::")) {
    Write-Host "FAIL: the port is bound to a wildcard address (LAN-reachable)."
    $fails++
}
else {
    Write-Host "OK: bound to loopback addresses only."
}

# 2. Other-device probe — connect to this machine's LAN IP (what another
#    device would target). Must fail.
$lanIp = (Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } |
    Select-Object -First 1).IPAddress
if (-not $lanIp) {
    Write-Host "WARN: no LAN IP found; skipping the other-device probe."
}
else {
    $probe = Test-NetConnection -ComputerName $lanIp -Port $Port -WarningAction SilentlyContinue
    if ($probe.TcpTestSucceeded) {
        Write-Host ("FAIL: {0}:{1} is reachable (LAN exposure!)." -f $lanIp, $Port)
        $fails++
    }
    else {
        Write-Host ("OK: {0}:{1} is unreachable (refused/blocked) as required." -f $lanIp, $Port)
    }
}

# 3. Positive control — CDP must answer on loopback.
try {
    $resp = Invoke-RestMethod -Uri ("http://127.0.0.1:{0}/json/version" -f $Port) -TimeoutSec 10
    Write-Host ("OK: CDP answers on 127.0.0.1:{0} -> {1}" -f $Port, $resp.Browser)
}
catch {
    Write-Host ("FAIL: CDP does not answer on 127.0.0.1:{0} ({1})" -f $Port, $_.Exception.Message)
    $fails++
}

if ($fails -eq 0) { Write-Host "LOOPBACK TEST: PASS"; exit 0 }
Write-Host "LOOPBACK TEST: FAIL"
exit 1
