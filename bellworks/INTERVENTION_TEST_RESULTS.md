# Physics Intervention — implementation and verification

## Recoverable baseline

Before editing application files, the clean revision `0f8d6c03d0709106674becd4b4abb721bd360e39` was tagged **`bellworks-before-intervention-20261015`**. A complete-history Git bundle was created and verified with `git bundle verify`, and the pre-change offline ZIP was copied separately. Local backups remain in the ignored `releases/` directory. The Git tag preserves the prior source and tracked offline package on GitHub. Metadata and the original ZIP's SHA-256 are in `snapshots/before-intervention.json`.

To recover the prior version, download the repository or `bellworks/Bellworks.zip` at [the baseline tag](https://github.com/gordonlu731/AI/tree/bellworks-before-intervention-20261015). A separate clone can also use `git clone --branch bellworks-before-intervention-20261015 <repository-url> Bellworks-baseline`.

## Behavior

- **Remove Domino:** removes the existing final, full-width gate domino, tile #08. The rigid body and its attached collider are removed from Rapier, its rendering piece is removed, and it is excluded from the active domino array. The other seven dominoes retain their baseline positions and colliders.
- **Add Obstacle:** adds a fixed red box at x = −7.9 on the first descent, upstream of the first domino. Its size is 0.26 × 1.5 × 2.4 world units; its bottom overlaps the floor and its width spans both rails. The visible box uses the same rigid-body transform and dimensions as the collider.
- Switches apply immediately to a rebuilt, unstarted world. Once a run has started, changes are queued for **Reset**, including while paused. This prevents mid-run edits from teleporting bodies or removing a contact under a moving ball.
- Start, Pause/Resume, Reset, camera controls, speed and sound remain available. Reset keeps the selected options, camera angle and speed. Clearing both options and resetting restores the baseline world.
- The stage observer is unchanged. Obstacle contact is counted from Rapier collision-start events and reported for diagnostics. There are no scripted failures, extra stage transitions, forced velocities, simulation stops, or intervention timers.

## Scenarios actually executed

The physics suite used the real Rapier world for **30 simulated seconds per run**, including interrupted runs. All settings below were repeated three times in Node. Browser tests separately repeated A, B and C three times through the actual UI, with 30 seconds advanced by the identical fixed-step solver per run. D and the combined options were also tested in the browser.

| Scenario | Node runs | Browser runs | Observed outcome |
| --- | ---: | ---: | --- |
| A. Default settings | 3 | 3 | All 9 stages complete; first mallet–bell collision at **14.825 s** |
| B. Add Obstacle enabled | 3 | 3 | Actual ball–barrier contact at **1.225 s**; ball remains upstream; only stage 1 triggers; no bell hit |
| C. Obstacle disabled again | 3 | 3 | All 9 stages complete again at **14.825 s**, with exactly the original stage timestamps |
| D. Final domino removed | 3 | 1 | Seven physical and visible dominoes remain; all 9 stages still complete; bell at **12.967 s** |
| Both options enabled | 3 | 1 | Domino is absent and red barrier still physically stops the ball; only stage 1 triggers |

**Removing the domino does not stop this machine.** Tile #08 is a full-width gate across the runway. Its removal opens the route, and the same steel ball can continue through the other passive mechanisms. The bell rings sooner in these measured runs. No failure was added to make the removal appear disruptive.

## Assertions and evidence

`npm run test:interventions` — **passed**, 15 scenario runs:

- Every default/restored run compared all nine timestamps exactly against those recorded from the pre-change revision.
- Obstacle runs tracked the ball's maximum x over every solver step. It stayed at or upstream of x = −8.32, with its resting center about x = −8.350. Tests also inspected a real final Rapier contact manifold between ball and barrier, not just a custom flag.
- Interrupted worlds continued to 30 seconds of simulated time while downstream stages remained untouched.
- Removal checks verified the old generation-bearing body/collider handles were gone and no corresponding rendering piece remained. Rapier may reuse the storage slot for the new obstacle; tests account for its different generation-bearing handle.

`npm run test:interventions:browser` — **passed**, 11 scenario runs:

- Toggled both real controls and used Reset to apply settings.
- Inspected live rendered mesh groups: 8 → 7 → 8 visible dominoes, and obstacle mesh absent → present → absent.
- Paused a blocked world, changed the obstacle switch, and verified the entire report and visible barrier stayed unchanged until Reset. The queued-settings message was shown.
- Checked one-click pre-release addition/removal of the visible barrier, independent combined settings, stage tracker counts and pause stability.
- Operated both controls at a 390 × 844 viewport and captured screenshots.
- Zero browser page/console errors and zero external runtime requests, with all non-loopback requests intercepted and blocked.

Machine-readable results: `artifacts/intervention-physics.json` and `artifacts/intervention-browser.json`. Screenshots: `artifacts/intervention-ready.png`, `artifacts/intervention-obstacle-contact.png`, `artifacts/intervention-domino-removed.png` and `artifacts/intervention-mobile.png`. The offline ZIP includes these in `evidence/`.

The original `npm run test:browser` suite also passed after the feature was added: a real-animation-loop baseline run, two reset runs, Pause/Resume, slow motion, orbit, zoom, pan, overhead, follow, mute and mobile layout. It reported zero page/console errors and zero external requests.

The original `npm run test:physics` regression suite also passed: three complete baseline runs, the unreleased-ball control and the immobilized-final-domino control. The latter is different from removing a domino: holding the gate upright blocks the runway, while removing it opens the runway. `npm run build` passed.

## Limits

Tests ran in Linux Chromium with SwiftShader and Node.js 24.19.0; native Windows Chrome was not available. Intervention matrix browser runs use an explicit test-only fixed-step accelerator and are not claimed to be real-time rendered runs. All times above are **simulation time**. For the original real-animation-loop and camera/speed control regression, see the current `artifacts/browser-results.json` and the recorded baseline report in `TEST_RESULTS.md`. No stages are marked failed merely because a run is blocked: the tracker continues to display only observed triggers.
