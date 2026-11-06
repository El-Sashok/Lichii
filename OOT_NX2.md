# Ocarina of Time (2026) on the `oot-nx2` branch

Fork of [zortos293/Lichii](https://github.com/zortos293/Lichii), branch `oot-nx2` on top of
upstream `nx2`. Goal: The Legend of Zelda: Ocarina of Time (2026, title `0400486024DEC000`) at a
steady 60 FPS on a fast desktop GPU. Measured on a Ryzen 9 9950X3D + RTX 5090 (Fedora 44,
Hyprland): 58 to 60 FPS while running, rolling and swinging the sword in Kokiri Forest, where
upstream `nx2` dipped to 40 to 50.

## What the branch changes

Everything is on by default. Each change keeps an environment switch to turn it off when
hunting a visual regression.

| Change | Switch (value to turn it off) |
| --- | --- |
| Macro DMA reads of query results wait for the host result before the macro reads them (fixes the white vegetation flashes). | `EDEN_NX2_QUERY_DMA_WAIT=0` |
| Macro DMA reads of report memory run on the split's front without draining the back (port of upstream PR 243). | `EDEN_NX2_DMA_EARLY=0`, `EDEN_NX2_DMA_EARLY_WAIT_WRITERS=1` waits for queued dispatches first |
| Semaphore acquires are predicted from the releases queued for the back (compute releases, inline QMD descriptors, fence payloads); an acquire whose word is final and unmet registers its wait without draining. | `EDEN_NX2_PREDICT_ACQUIRES=0` |
| Command lists wait only for the dispatches and copies sent before the guest's last sync point before their GPU-written check. | `EDEN_NX2_LIST_SYNCED_WRITERS=0` |
| New depth and color render targets skip their upload from guest memory unless a copy engine wrote their pages or the cache downloaded them. | `EDEN_NX2_SKIP_DEPTH_UPLOAD=0`, `EDEN_NX2_SKIP_COLOR_UPLOAD=0` |
| A render target bound over an image unused for more than 2 frames deletes it instead of keeping both as a bad overlap (the game ring-allocates its transient targets, the cache held ~100 dead images per slot). | `EDEN_NX2_RT_EVICT_OVERLAPS=0` (or `=<frames>`) |
| Texture cache collector: images used in the last 150 frames are never evicted; a card with more than 6.7 GiB of memory may fill three quarters of it before the collector downloads evicted targets. | `EDEN_NX2_TC_MIN_AGE=<frames>`, `EDEN_NX2_TC_EXPECTED_MIB`, `EDEN_NX2_TC_CRITICAL_MIB` |
| Pages the CPU reads often are copied back at every fence instead of flushing on each read. | `EDEN_NX2_PREFLUSH=0`, `EDEN_NX2_PREFLUSH_HOT_MS=<ms>` |
| Built pipelines are kept (no eviction). | `EDEN_NX2_PIPELINE_EVICT_FRAMES=<frames>` |

Logs (`eden_log.txt`, level Info): `NX2 MME DMA reads`, `NX2 acquires`, `NX2 QMD mirror`,
and with `EDEN_NX2_TC_LOG=1` the texture cache's memory, creations, uploads and shapes every
600 frames. `EDEN_DKB_FRAME_TRACE=1` prints one line per second with the frame count and the
GPU threads' CPU time per frame.

## Build (Linux)

Follow [docs/Build.md](docs/Build.md) and [docs/Deps.md](docs/Deps.md). The plain build works:

```sh
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build --target lichii
```

The measured binary was built with clang 23, `-march=native`, ThinLTO and a PGO profile, with
the bundled Vulkan headers (`-DVulkanHeaders_FORCE_BUNDLED=ON
-DVulkanUtilityLibraries_FORCE_BUNDLED=ON`). None of that is required: the gains come from the
code, the optimized build is worth a few percent.

## Run

Launch command used for every measurement (a `.desktop` `Exec=` line works the same):

```sh
env QT_QPA_PLATFORM=xcb EDEN_NX2_PRELOAD_ALL_PIPELINES=1 ./build/bin/lichii "<path to the title>"
```

- `QT_QPA_PLATFORM=xcb`: on Wayland (Hyprland) the native Qt platform crashes at exit.
- `EDEN_NX2_PRELOAD_ALL_PIPELINES=1`: builds every cached pipeline at boot instead of on first
  use, so the shader cache does not stutter in the first minutes of play. Longer boot.
- CPU pinning (`taskset`) made no measurable difference.

Emulator settings (Configure > Graphics / Advanced / CPU), all other values at their defaults:
Vulkan, resolution 1x, VSync FIFO, scaling filter ScaleForce, anti-aliasing FXAA, GPU accuracy
Normal, VRAM usage aggressive, ASTC decoding GPU, NVDEC on CPU, asynchronous GPU emulation,
asynchronous shaders, reactive flushing, async presentation, disk shader cache, CPU accuracy
Auto, speed limit 100 %.

## Measuring

`tools/nx2/oot/ab_cycle.sh <label> [ENV=VALUE ...]` restarts the emulator with the debug server,
loads the save (4 presses of A: intro skip, then the file menu), then replays a 30 s course three
times (forward with rolls, camera sweep, strafe with sword) and prints per pass the FPS minimum,
p10, p25, median and mean, the back thread's CPU time per frame and the host waits:

```sh
LICHII_GAME="<path to the title>" tools/nx2/oot/ab_cycle.sh baseline
LICHII_GAME="<path to the title>" tools/nx2/oot/ab_cycle.sh no-evict EDEN_NX2_RT_EVICT_OVERLAPS=0
```

The save must start in game, outdoors. Judge on the first pass: the second and third replay the
same inputs over a warm cache, and the game's allocator repeats its addresses, so they measure
less than real play does. `LICHII_BIN`, `LICHII_OUT` and `LICHII_LOG` override the binary, the
output directory (`/tmp/lichii-oot`) and the log path. Do not compare FPS with
`EDEN_NX2_GPU_PROFILE=1`: its per-site wait report costs frames.
