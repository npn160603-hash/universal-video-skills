# UVS local API — example requests and responses

Start the server (loopback only):

    python3 -m uvs.server /path/to/workspace --port 8721

## GET /v1/info
Response:
```json
{"api_version": "1.0.0", "workspace": "/path/to/workspace",
 "styles": ["cinematic_documentary", "..."], "genres": ["real_life_storytelling", "..."],
 "capabilities": ["analyze", "plan", "index_media", "retrieve", "select_style",
                  "generate_timeline", "render_chart", "captions", "qa"]}
```

## POST /v1/generate_timeline
Request:
```json
{"words": [{"text": "We", "start": 0.0, "end": 0.3}, {"text": "learn", "start": 0.3, "end": 0.7}],
 "style": "emotional_storytelling", "genre": "real_life_storytelling", "fps": 30,
 "width": 1080, "height": 1920,
 "capabilities": {"maps": true, "charts": true, "broll_library": false},
 "overrides": {"S01": {"transition": "dissolve"}}}
```
Response (abridged):
```json
{"style": "emotional_storytelling",
 "decisions": [{"scene_id": "S01", "selected": {"shot_duration_s": 3.3, "transition": "dissolve", "...": "..."},
                "scores": {"narrative_relevance": 0.9, "...": 0.8}, "relevance_score": 0.88,
                "confidence": 0.9, "overridden_fields": ["transition"]}],
 "instructions": [{"scene_id": "S01", "start_frame": 0, "duration_frames": 99, "look": "soft_romantic_v2"}]}
```

## POST /v1/render_chart  (returns a job)
Request:
```json
{"spec": {"kind": "comparison", "categories": ["2023", "2024"],
          "series": [{"label": "Revenue", "values": [120, 180]}], "source": "demo"},
 "out": "charts/revenue.mp4", "fps": 30}
```
Response:
```json
{"job_id": "a1b2c3d4e5f6a7b8"}
```

## GET /v1/jobs/<id>
```json
{"id": "a1b2c3d4e5f6a7b8", "kind": "render_chart", "status": "succeeded",
 "progress": 1.0, "outputs": ["/path/to/workspace/charts/revenue.mp4"], "duration_s": 2.1}
```

## Errors
All errors are JSON: `{"error": "message"}` with HTTP 400 (bad request), 404 (unknown id) or 500.
