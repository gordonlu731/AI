# Verification — The Bellworks

Verified on **2026-10-15** in the Linux cloud workspace, using Node.js 24.19.0 and the installed headless Chromium with SwiftShader. Windows Chrome is the intended delivery platform; a native Windows session was **not** available and was not tested.

## Final physics revision

`npm run test:physics` — **passed**.

- **Three complete independent world creations / runs**, all nine stages observed in chronological order in every run.
- First mallet–bell collision at **14.825 simulated seconds**, identical across the three runs.
- Collision events confirmed the ball touched the gate, wheel, seesaw, bucket and hammer.
- The bell's completion flag requires **hammer–bell contact**, not proximity, an elapsed-time threshold or a ball-only impact.
- **Unreleased control:** ran the solver for 15 simulated seconds with the initial ball still fixed. Zero stages and zero bell strikes.
- **Blocked-path control:** immobilized the full-width final domino and ran for 22 seconds. The pendulum and bell never triggered. This checks that the domino passage is a real physical prerequisite.

| Stage | Trigger in successful runs | Result |
| --- | ---: | --- |
| 1. Gravity runway | 0.992 s | PASS |
| 2. Domino cascade | 3.125 s | PASS |
| 3. Pendulum gate | 4.242 s | PASS |
| 4. Descending half spiral | 9.133 s | PASS |
| 5. Paddle wheel | 10.975 s | PASS |
| 6. Seesaw bridge | 12.067 s | PASS |
| 7. Tipping bucket | 13.525 s | PASS |
| 8. Suspended mallet | 14.717 s | PASS |
| 9. Bell impact | 14.825 s | PASS |

Stage timestamps indicate the observed trigger, not when every body has finished settling. Domino tracking requires at least six tiles to topple; the full-width final tile remains a physical obstruction until it falls.

## Production browser checks

`TEST_URL=http://127.0.0.1:4174 node tests/browser.mjs` against `node tools/serve.mjs` — **passed**.

- One complete run using the actual animation loop at normal speed, with pause / resume during the run.
- Two more complete runs after resetting, using the test-only fixed-step accelerator; the third selects slow mode. Every stage timestamp matched the real animation-loop run.
- The accelerator executes Rapier steps without rendering every intermediate frame. These two runs validate browser physics and reset repeatability; they are **not** described as real-time rendered runs.
- Pause held simulation time, ball position, velocity, stage flags and contact report exactly constant.
- Reset restored the original position, cleared all flags and bell strikes, and enabled Start again.
- Normal versus slow motion advanced different amounts of simulation time over equal wall intervals; slow mode uses a 0.25 multiplier and the same 120 Hz solver.
- Camera orbit, scroll zoom, right-drag pan and overhead controls changed the camera as expected. Follow and sound-toggle state controls responded.
- Desktop (1440 × 1000) and mobile (390 × 844) screenshots captured and inspected. The mobile Start control stays within the viewport.
- **Zero page exceptions and zero console errors.**
- **Zero external runtime requests.** The test intercepted and blocked all non-loopback network requests; loading and all three complete runs still succeeded.

Machine-readable output: `artifacts/browser-results.json`. Physics log: `artifacts/physics-results.txt`. Captures: `artifacts/initial.png`, `artifacts/in-motion.png`, `artifacts/completed.png`, `artifacts/mobile.png`. The downloadable archive includes these under `evidence/`.

## Installation, build and offline serving

- `npm --cache /tmp/npm-cache ci --offline --no-audit --no-fund` — passed using the populated local package cache, confirming lockfile installation after deleting / recreating `node_modules`.
- `npm run build` — passed. Complete production output is in `dist/`.
- Dependency-free Node HTTP server — served HTML, JavaScript, CSS and favicon successfully to the browser tests. No npm package is needed to serve the prebuilt application.
- Rapier WASM is embedded in its approximately 2.85 MB local physics JavaScript chunk. Three.js is a separate local graphics chunk. Fonts, materials, lettering, environment and sound use no network assets.

## Diagnosed issues corrected during implementation

Initial iterations had self-toppling tiles, a pile of tiles obstructing the ball, tray / railing interference, and an insufficient drop below the tray. These were corrected through collider placement, stable tile feet, a full-width final gate tile, clearance around the tipping tray and a lower receiving track. Final runs have no failing stages.

## Remaining limitations

- Native Windows Chrome execution and audible speaker output were not tested in this Linux environment. Audio initialization and mute controls were exercised, but headless Chromium mutes playback.
- Software graphics rendering here runs slower than wall-clock time; **14.825 s is simulation time**, not a measured Windows frame-rate claim. Hardware-accelerated Chrome is recommended.
- The bell collision shape is a solid convex hull matching its outer profile. Its sound is synthesized rather than an acoustic simulation.
- The return is a railed, descending half-turn rather than a multi-turn funnel. The sculpture uses passive mechanisms and a single continuous ball route.
- The ready-to-run distribution is offline. Rebuilding source on a new machine requires either an initial npm installation with internet access or a populated npm cache. Node and Chrome must already be installed.
