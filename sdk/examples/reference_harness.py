"""Reference harness for the UVS local API (Phase 12).

A MINIMAL SAMPLE that demonstrates the editor flow: send a script, pick a style, generate a
timeline, submit a render, poll progress, and read the output path. It is a demonstration only.
It is NOT an integration with any specific editor, and must not be presented as one.

    python3 sdk/examples/reference_harness.py /path/to/workspace
"""
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from uvs.api import UVSApi           # noqa: E402
from uvs.server import make_server   # noqa: E402
from uvs.sdk import UVSClient        # noqa: E402


def main(workspace: str) -> int:
    api = UVSApi(workspace)
    srv = make_server(api, "127.0.0.1", 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    time.sleep(0.2)
    cli = UVSClient(f"http://127.0.0.1:{srv.server_address[1]}")

    print("[sample] 1. server info:", cli.info()["api_version"])
    words = [{"text": w, "start": i * 0.4, "end": i * 0.4 + 0.35}
             for i, w in enumerate("We learn to say no and everything changes".split())]
    print("[sample] 2. styles available:", len(cli.styles()))
    tl = cli.generate_timeline(words, "emotional_storytelling")
    print(f"[sample] 3. timeline: {len(tl['instructions'])} scenes, QA ok={cli.qa(tl)['ok']}")
    job = cli.render_chart({"kind": "counter", "categories": [],
                            "series": [{"label": "subscribers", "values": [125000]}],
                            "source": "sample", "width": 480, "height": 270, "duration": 1.0},
                           "charts/counter.mp4", fps=24)
    print("[sample] 4. render job:", job)
    st = cli.wait_for_job(job, timeout=30)
    print(f"[sample] 5. render {st['status']}; output: {st['outputs']}")
    srv.shutdown()
    print("[sample] done. This is a demonstration harness, not an editor integration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "/tmp/uvs_workspace"))
