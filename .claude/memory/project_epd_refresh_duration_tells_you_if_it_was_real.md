---
name: project_epd_refresh_duration_tells_you_if_it_was_real
description: On the 7in3f panel a real refresh takes ~62s; a 12s "EPD updated" is a silent no-op
metadata:
  type: project
---

`EPD updated.` in the log does **not** mean pixels changed. On the Waveshare 7.3" 7-colour
panel (`waveshare_epd.epd7in3f`), time the gap between `Displaying on EPD...` and
`EPD updated.`:

| Gap | Meaning |
|---|---|
| ~62-65s | Real refresh. `clear()` ~31s + `display()` ~31s, both close to the datasheet's ~35s full refresh. |
| ~8-12s | **No-op.** The calls returned without driving the panel. The log still says success. |

Measured 2026-08-29: identical image and code path gave 12s (nothing appeared) and later 65s
(appeared). Content does not affect the timing, `clear()` does not even look at the image, so a
fast refresh is never explained by "the image was mostly white".

The panel had been stuck in the no-op state since that morning's boot loop, where each cycle
powered off about 15s after starting a refresh that needs 62s, cutting the panel off mid-write
every time. One full uninterrupted refresh cleared the state and it stayed healthy afterwards.

So when the display looks frozen, **check the duration before believing the logs**, and suspect
anything that can cut power or kill the process mid-refresh. Related:
[[project_service_name_and_seq_only_logs]].
