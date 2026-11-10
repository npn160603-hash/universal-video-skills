# Motion demo

Synthetic scene: a red card that fades in, slides and turns, plus a yellow dot that grows and shrinks.
Both are plain shapes; no footage or licensed material is used.

    python3 -m uvs.animate examples/motion_demo/scene.json examples/motion_demo/animation.json \
        --out out/motion_demo.mp4 --fps 30 --duration 2 --width 1280 --height 720

Expected: 60 frames, 1280x720, 2.000 s. At 0.25 s the card is at half opacity. At 1.9 s it is
nearly vertical. The dot is at scale 1.5 from 1.0 s.
