# The Bellworks

An interactive, nine-stage Rube Goldberg sculpture. One steel ball descends a two-level, three-dimensional brass-and-timber machine, drives its passive mechanisms, and swings a mallet into a hanging bell.

**Three.js 0.186.0 · Rapier 3D compat 0.20.0 · Vite · npm**

## Run the finished application offline

1. Install Node.js 22 LTS or newer on the computer in advance.
2. Extract the delivered project, keeping `dist/` and `tools/` beside `start-offline.bat`.
3. On Windows, double-click **`start-offline.bat`**. Alternatively, run:

   ```sh
   node tools/serve.mjs
   ```

4. Open Chrome at **http://127.0.0.1:4173**.

This path requires **no npm installation and no internet connection**. Three.js, Rapier's embedded WASM, application code, styles, and favicon are already in `dist/`. Materials, lettering, environment lighting, and the bell sound are generated locally. The dependency-free server uses only Node's built-in modules. Keep the terminal open; Ctrl+C stops the server. Set `PORT` to change its port.

Use a local HTTP server rather than double-clicking `dist/index.html`: Chrome restricts ES modules on `file://` pages.

## Install and develop

When using the `AI` repository checkout, first enter the project with `cd bellworks`. When using the standalone ZIP, use its extracted `Bellworks` folder directly. All commands below assume that project directory.

Use Node.js **22.12+** (24 also works) and npm. Initial dependency installation needs access to the npm registry; running the resulting application does not.

```sh
npm ci
npm run dev
```

Open http://localhost:5173. All dependencies have exact versions in `package.json` and `package-lock.json`.

```sh
npm run build       # regenerate the complete dist directory
npm run preview     # inspect the production build on port 4173
npm run offline     # serve dist using only built-in Node modules
```

The physics chunk is intentionally larger than typical web code: `rapier3d-compat` embeds its WASM into the local JavaScript bundle. It does not download a WASM binary at runtime.

## Controls

| Control | Action |
| --- | --- |
| Release the ball | Unlock the initial steel ball; gravity supplies the energy |
| Pause / Resume | Freeze / resume the complete physics world |
| Reset | Recreate all rigid bodies, joints, collision state, stage flags and elapsed time |
| Normal / Slow | 1× or ¼× simulation time; solver step remains 1/120 second |
| Left-drag | Orbit |
| Right-drag | Pan |
| Scroll | Zoom |
| Crosshair / overhead / target buttons | Home view / top view / follow the ball |
| Musical note | Toggle locally synthesized bell audio |
| Space | Release, then pause / resume (when a button does not have keyboard focus) |

The tracker observes actual motion and contacts. The final message and sound are produced only by a physical **mallet–bell contact**. The simulation keeps running after completion so the bell and other mechanisms can settle. The displayed finish time records the first strike. Reset keeps the current camera angle and selected speed.

## The nine stages

| # | Mechanism | Physical connection |
| --- | --- | --- |
| 1 | Gravity runway | Release the ball onto a high, sloping railed track |
| 2 | Eight dominoes | The ball topples the first tile; collisions carry the cascade down the row; the full-width final tile must fall to open the runway |
| 3 | Pendulum gate | The same ball strikes a hanging gate and swings it out of the way |
| 4 | Descending half spiral | A 180° sloping return redirects the ball through depth onto a lower, reversed runway |
| 5 | Paddle wheel | The ball turns a four-blade wheel on a revolute axle |
| 6 | Seesaw bridge | The ball traverses a counterweighted, joint-limited lever spanning a real track gap |
| 7 | Tipping bucket | The ball loads a lipped tray, shifting its balance; the tray tips and drops it onto a lower receiving track |
| 8 | Suspended mallet | The arriving ball transfers momentum to a freely hinged hammer |
| 9 | Hanging bell | The hammer's forward arc hits the bell's convex rigid-body collider; the bell swings and rings |

Eight stages precede the final bell. Mechanisms use gravity, collision response, and passive revolute joints. There are **no stage motors, scripted impulses, object teleports, predetermined animations, or timed releases**. Stage observations never alter the physics. The one start operation changes the ball from fixed to dynamic. Decorative supports are separate from the travel surfaces; all moving mechanisms and travel surfaces have physical colliders.

## Validation

```sh
npm run test:physics
npm run build
# Start npm run offline in a separate terminal, then:
npm run test:browser
```

Browser tests use Playwright and an existing Chrome/Chromium. On Linux they default to `/usr/bin/chromium`; elsewhere Playwright's installed Chromium is used. Override with `CHROME_PATH`, or install Playwright Chromium with `npx playwright install chromium`. Windows PowerShell example:

```powershell
$env:CHROME_PATH = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
npm run test:browser
```

`TEST_URL` can target another local port. Browser tests reject every non-loopback request and test the production build. They save screenshots and machine-readable results in `artifacts/`. Read [TEST_RESULTS.md](TEST_RESULTS.md) for the checks actually performed and their limitations.

## Project layout

- `src/machine.js` — renderer-independent Rapier world, geometry, joints, contact observations.
- `src/scene.js` — Three.js studio, procedural sculpture, lighting, shadows, camera and static-geometry batching.
- `src/main.js` — fixed-step loop, controls, stage display and synthesized audio.
- `src/style.css` — responsive interface; only system fonts.
- `tools/serve.mjs` — no-dependency offline static server.
- `tests/` — physics and browser regression checks.
- `dist/` — production application, ready for offline serving.

`?test=1` exposes an explicit test-only fixed-step accelerator. It runs exactly the same solver; it cannot assign stages, reposition objects, or inject impulses. Normal pages expose only read-only diagnostic snapshots at `window.__bellworks`.

## Practical limits

Chrome with WebGL2 and working graphics drivers is required. Hardware acceleration is recommended; software-rendered browsers can take longer than wall-clock time to simulate a run. The fixed-step accumulator caps catch-up after a stall, and returning from a hidden tab does not fast-forward the machine. The bell uses a convex hull of its visible profile, with a solid interior, rather than a hollow acoustic shell. Sound is a local synthesized bell tone, not acoustic simulation. The return stage is a descending half-turn, not a multi-turn funnel. No assets or services are hosted externally.
