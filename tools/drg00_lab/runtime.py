from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


IMAGE = "python:3.12@sha256:a116514e19457bcb7af7efe9c3dd0b9b71e85b317694e7882a1c52aa15a78134"


def validate_compose(path: Path) -> list[str]:
    """Validador cerrado del subconjunto de Compose usado por el laboratorio."""
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    required = (
        f"image: {IMAGE}", "network_mode: none", "read_only: true",
        'user: "65532:65532"', "cap_drop:", "- ALL",
        "no-new-privileges:true", "pull_policy: never",
    )
    for token in required:
        if token not in text:
            errors.append(f"missing:{token}")
    for forbidden in ("ports:", "network_mode: host", "privileged: true",
                      "/var/run/docker.sock", "pid: host", "ipc: host"):
        if forbidden in text:
            errors.append(f"forbidden:{forbidden}")
    if text.count("network_mode: none") != 2:
        errors.append("exactly_two_isolated_services_required")
    return errors


def run_network_probe(service: str) -> dict[str, object]:
    if service not in {"quarantine", "processing"}:
        raise ValueError("unknown isolated service")
    program = (
        "import json,os,socket;"
        "dns=False;tcp=False;root_write=False;tmp_write=False;"
        "\ntry:\n socket.getaddrinfo('example.com',443);dns=True\nexcept OSError: pass"
        "\ntry:\n s=socket.create_connection(('1.1.1.1',443),.25);s.close();tcp=True\nexcept OSError: pass"
        "\ntry:\n open('/forbidden','w').write('x');root_write=True\nexcept OSError: pass"
        "\ntry:\n open('/tmp/proof','w').write('x');tmp_write=True\nexcept OSError: pass"
        "\nprint(json.dumps({'dns_external':dns,'tcp_external':tcp,'root_write':root_write,'tmp_write':tmp_write,'uid':os.getuid()}))"
    )
    command = [
        "docker", "run", "--rm", "--pull", "never", "--network", "none",
        "--read-only", "--user", "65532:65532", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges:true", "--pids-limit", "64",
        "--memory", "64m", "--cpus", "0.5", "--tmpfs",
        "/tmp:rw,noexec,nosuid,nodev,size=8m", "--label",
        f"fincilia.zone={service}", IMAGE, "python", "-c", program,
    ]
    completed = subprocess.run(
        command, capture_output=True, text=True, timeout=30, check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"isolated runtime probe failed: {completed.stderr.strip()}")
    payload = json.loads(completed.stdout)
    expected = {
        "dns_external": False, "tcp_external": False,
        "root_write": False, "tmp_write": True, "uid": 65532,
    }
    if payload != expected:
        raise RuntimeError(f"isolation invariant failed: {payload}")
    return {"service": service, **payload}


def main() -> int:
    try:
        result = [run_network_probe(service) for service in ("quarantine", "processing")]
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, sort_keys=True))
        return 1
    print(json.dumps({"ok": True, "probes": result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
