# Live browser facial index

The UI no longer accepts or displays a questionnaire stress rating. Open Live, consent to local camera processing, enable the camera, then choose Calibrate and start live graph. Relax, face the camera and stay quiet for the first 25 seconds.

After calibration, a fixed mathematical facial index updates on camera frames at up to 10 Hz; the graph samples about once per second. The requested axis is 0 = high stress, 10 = no stress. These are experimental labels, not clinical measurements. The transformation is (100 - S)/10, so baseline feature means map to 5/10, not 10. Facial expression changes cannot establish how stressed an individual is.

The browser uses MediaPipe Face Landmarker, the canonical 75-point reference and a 2-D similarity alignment. Geometric features, blink events, and 5-second pose/landmark motion variability feed the fixed index. Effective sigma = max(raw sigma, 0.05 * abs(mu) + 1e-3), z clips to [-3,3], equal weights, rolling 5-second aggregation, alpha=.1 EMA. Pulse/HRV is omitted. Browser pose comes from the approximate MediaPipe transformation matrix rather than Python solvePnP, so full detector/pipeline parity is not established.

No reading is emitted before calibration. Baseline requires at least 30 usable frames and 40% usable coverage. Frames with poor brightness/framing, multiple/missing faces, absolute yaw/pitch >35 degrees, MAR>.35 or smile-corner gate are withheld. The graph breaks at unavailable readings. Aggregate results are withheld below 40% post-calibration coverage or without any score samples.

Sessions end on Finish, Cancel, navigation, tab hiding, errors, or the five-minute limit. Browser recording is never enabled; no video or landmarks are uploaded or persisted. Saving graph time/value samples and summary requires an explicit checkbox. These sessions use pause-camera-sessions-v2 storage, separate from existing pause-checkins-v1 questionnaire history, which is preserved. No Gemini call is made by the current UI.

Verification: six Node tests, synthetic Python/JavaScript geometric-feature and score parity, graph gap/label/accessibility rendering, and production build passed. Browser UI contains no stress-rating input and requires camera consent. Real webcam behavior and real-dataset accuracy remain unverified.

Run tests: node --test frontend/src/liveIndex.test.js

MediaPipe output/pose references: https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker/web_js and https://github.com/google-ai-edge/mediapipe/blob/master/mediapipe/framework/formats/matrix_data.proto. The derived canonical reference uses MediaPipe's Apache-2.0 asset; public/LICENSE.mediapipe includes its license.
