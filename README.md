# Secure Agent Sandbox

Secure Agent Sandbox runs repository work inside a disposable Docker container
based on Python 3.14. The host workspace is mounted at `/workspace` so changes
remain available after the container is destroyed.

## CLI

Install Docker Desktop with Docker Sandboxes (`sbx` version 0.42 or newer),
then install the local CLI:

```powershell
python -m pip install -e .
sas create
sas status
sas shell
sas exec python --version
sas import .\sample.zip
sas exec file /sas/incoming/sample.zip
sas export /sas/outgoing/report.zip .\reports
sas destroy
```

`create` creates a **mountless** Docker Sandbox: no host directory is passed to
`sbx`, so the sandbox cannot see the project directory or other host files.
Files cross the boundary only through the explicit `import` and `export`
commands. Imported files are placed below `/sas/incoming`; exports are allowed
only from `/sas/outgoing`.

The sandbox is isolated by Docker's microVM architecture, but it is not a
guarantee against resources explicitly shared by the user. Do not enable
workspace mounts, local MCP servers, shared writable skills, host credentials,
or published ports for untrusted files or agents. Select Docker's **Locked
Down** network policy for offline malware/file testing and verify it with
`sbx policy ls`. The CLI does not silently configure global Docker policy.

`Dockerfile` is retained as a legacy build artifact for now; it is not used as
the isolation boundary by `sas`.
