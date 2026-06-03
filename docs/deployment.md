# Deployment Guide

Production deployment of `swiss-ip-mcp` over the Streamable HTTP transport.
Addresses audit findings **SEC-007** (sandboxing), **SCALE-002 / SCALE-003**
(session routing), **SCALE-004** (containerization) and **SCALE-006** (resource
limits).

> The HTTP endpoint is **unauthenticated** and serves only public IP-register
> data. Do not place credentialed or non-public tools behind it without adding
> authentication first.

## Container image (SCALE-004)

The [`Dockerfile`](../Dockerfile) is a two-stage build:

- **builder** installs the package into an isolated `/opt/venv`.
- **runtime** is `python:3.12-slim`, copies only the venv, runs as a non-root
  user (UID/GID `10001`), and ships a `HEALTHCHECK` that probes `/health`.

```bash
docker build -t swiss-ip-mcp:latest .
docker run --rm -p 8000:8000 \
  -e IGE_USERNAME=... -e IGE_PASSWORD=... \
  swiss-ip-mcp:latest
```

The image defaults to `MCP_TRANSPORT=streamable-http`, `MCP_HOST=0.0.0.0`
(safe inside a container; `CONTAINER=1` is set so the loopback warning is
suppressed) and `MCP_STATELESS_HTTP=1`.

## Hardening (SEC-007)

| Control | Where |
|---------|-------|
| Non-root user, UID ≥ 10000 | `Dockerfile` (`USER 10001:10001`) |
| `no-new-privileges`, `cap_drop: ALL`, read-only rootfs, `tmpfs /tmp` | `docker-compose.yml` |
| `runAsNonRoot`, `runAsUser`, `allowPrivilegeEscalation: false` | `deploy/kubernetes/deployment.yaml` |
| `readOnlyRootFilesystem: true` + `emptyDir` for `/tmp` | same |
| `capabilities.drop: ["ALL"]`, `seccompProfile: RuntimeDefault` | same |

The server writes nothing to disk (`PYTHONDONTWRITEBYTECODE=1`), so a read-only
root filesystem works with only a writable `/tmp`.

## Resource limits (SCALE-006)

[`docker-compose.yml`](../docker-compose.yml): `mem_limit: 512m`,
`mem_reservation: 256m`, `cpus: 1.0`, `pids_limit: 256`, and `ulimits.nofile`
4096/8192. Kubernetes uses `requests` (cpu `100m` / mem `128Mi`) below `limits`
(cpu `1` / mem `512Mi`) to allow bursting, plus a `restart`/restart-policy so the
container recovers cleanly on OOM.

## Scaling & session routing (SCALE-002 / SCALE-003)

Two supported modes:

1. **Stateless (recommended, default in our images):** set
   `MCP_STATELESS_HTTP=1`. The server keeps no per-session state, so any replica
   can serve any request — plain round-robin load balancing, no affinity.
2. **Stateful:** unset `MCP_STATELESS_HTTP`. Then each `Mcp-Session-Id` must be
   pinned to one replica. Use the provided [`deploy/haproxy.cfg`](../deploy/haproxy.cfg),
   which keys a stick-table (capacity 100k, TTL 24h) on the `Mcp-Session-Id`
   header and health-checks backends via `/health`.

## Health endpoint

The HTTP app exposes `GET /health` → `200 {"status": "ok"}`, consumed by the
container `HEALTHCHECK`, Kubernetes readiness/liveness probes, and the HAProxy
backend check.

## Network egress (SEC-005 / SEC-021)

Two layers:

- **Code layer (SEC-021):** an immutable `ALLOWED_EGRESS_HOSTS` frozenset
  (`idp.ipi.ch`, `www.swissreg.ch`) is enforced by `_assert_host_allowed()`
  before *every* outgoing request. Any attempt to reach another host raises.
- **Network layer:** restrict egress to those two hosts via a NetworkPolicy /
  security group / egress proxy where possible.

For public deployments also set `MCP_ALLOWED_HOSTS` and `MCP_ALLOWED_ORIGINS`
to enable DNS-rebinding protection and scope CORS.
