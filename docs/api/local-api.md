# Local editor API and SDK (Phase 12) — public interface

Status: PARTIAL. Core API, job manager, localhost server, Python SDK, TypeScript client, harness.
Direct editor integration is BLOCKED (repository not identified).

## Core API (`uvs.api.UVSApi`)
Construct with a workspace root. Methods: `info`, `create_project`, `analyze_script`, `plan_narrative`, `index_media`, `retrieve_media`, `list_styles`, `select_style`, `generate_timeline`, `render_chart` (job), `render_captions`, `qa_timeline`, `job_status`, `cancel_job`, `retry_job`. All paths resolve under the workspace (traversal refused).

## Jobs (`uvs.jobs.JobManager`)
`submit`, `status`, `cancel`, `retry`, `wait`, `list_jobs`. States: queued, running, succeeded, failed, cancelled. Progress and cooperative cancellation via `JobHandle`.

## Server (`uvs.server`)
`make_server(api, host, port)` — loopback only. `serve(workspace, host, port)` / `python3 -m uvs.server <workspace>`. Routes under `/v1/` (see `sdk/examples/requests.md`). 4 MiB body cap; JSON errors.

## Python SDK (`uvs.sdk.UVSClient`)
Mirrors the API over HTTP; `wait_for_job`. TypeScript client: `sdk/typescript/uvs-client.ts` (type-checks under tsc --strict).

## Reference harness
`sdk/examples/reference_harness.py` — a labelled demonstration of the editor flow. Not an integration with any specific editor.

## Security
Loopback-only bind; path restriction; no shell-out on user input; body cap. Add an auth token before any non-loopback exposure.
