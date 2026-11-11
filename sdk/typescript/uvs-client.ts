// UVS local API client (TypeScript). Phase 12.
// A dependency-free client for the loopback JSON API in uvs/server.py.
// This talks only to a local UVS server you run yourself. It is a reference adapter for a local
// web editor, not an integration with any specific editor.

export type Word = { text: string; start: number; end: number };

export type JobStatus = {
  id: string;
  kind: string;
  status: "queued" | "running" | "succeeded" | "failed" | "cancelled";
  progress: number;
  message: string;
  error: string | null;
  outputs: string[];
};

export class UVSClient {
  constructor(private base = "http://127.0.0.1:8721", private timeoutMs = 120000) {}

  private async req<T>(method: string, path: string, body?: unknown): Promise<T> {
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), this.timeoutMs);
    try {
      const res = await fetch(`${this.base}${path}`, {
        method,
        headers: { "Content-Type": "application/json" },
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: ctl.signal,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(`${res.status}: ${(data as any).error ?? "error"}`);
      return data as T;
    } finally {
      clearTimeout(timer);
    }
  }

  info() { return this.req<Record<string, unknown>>("GET", "/v1/info"); }
  analyze(words: Word[], genre = "real_life_storytelling") { return this.req("POST", "/v1/analyze", { words, genre }); }
  plan(words: Word[], genre = "real_life_storytelling", title = "untitled") { return this.req("POST", "/v1/plan", { words, genre, title }); }
  styles() { return this.req<{ styles: unknown[] }>("POST", "/v1/styles", {}); }
  selectStyle(name: string) { return this.req("POST", "/v1/select_style", { name }); }
  generateTimeline(words: Word[], style: string, opts: Record<string, unknown> = {}) {
    return this.req("POST", "/v1/generate_timeline", { words, style, ...opts });
  }
  renderChart(spec: unknown, out: string, fps = 30) {
    return this.req<{ job_id: string }>("POST", "/v1/render_chart", { spec, out, fps });
  }
  qa(editPlan: unknown) { return this.req("POST", "/v1/qa", { edit_plan: editPlan }); }
  job(id: string) { return this.req<JobStatus>("GET", `/v1/jobs/${id}`); }
  cancel(id: string) { return this.req<JobStatus>("POST", `/v1/jobs/${id}/cancel`); }

  async waitForJob(id: string, timeoutMs = 120000, pollMs = 150): Promise<JobStatus> {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      const st = await this.job(id);
      if (["succeeded", "failed", "cancelled"].includes(st.status)) return st;
      await new Promise((r) => setTimeout(r, pollMs));
    }
    throw new Error(`job ${id} did not finish in time`);
  }
}
