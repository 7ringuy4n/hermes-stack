# Security isolation risks

- Timestamp: `2026-08-17 15:14:38 +0700`

- **sandbox_env**: pass — SECURITY_SANDBOX from .env
- **judge_env**: pass — SECURITY_LLM_JUDGE
- **av_env**: pass — ENABLE_ANTIVIRUS
- **traefik_mode**: pass — VPN-only default
- **sock_security_manager**: pass — no docker.sock
- **sock_zalo_api**: pass — no docker.sock
- **socket_proxy**: pass — proxy not running
- **health_sandbox**: pass — {"ok": true, "av": false, "llm_judge": false, "yara": true, "sandbox": false, "fail_closed": true, "docker_host": false}
- **health_judge**: pass — llm_judge flag
- **health_docker_host**: pass — docker_host
- **openbao_bind**: pass — check docker port openbao
- **hermes_no_host_dashboard**: pass — replicas≠1 must not publish :29119
- **scan_clean**: pass — 
{"verdict":"CLEAN","layers":{"archive":{"ok":true},"static":{"ok":true,"skipped":true},"yara":{"ok":true,"hits":[],"engine":"yara"},"antivirus":{"ok":true,"skipped":true,"reason":"av_disabled"},"llm_judge":{"ok":true,"skipped":true,"reas
- **scan_eicar_yara**: pass — EICAR must RISK via YARA-lite with AV off
- **scan_inject_judge**: pass — judge skipped/heuristic

Final: **PASS** (0 fail)
