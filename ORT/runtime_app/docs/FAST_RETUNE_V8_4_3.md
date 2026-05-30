# Fast Retune v8.4.3

This document records the user-approved Fast model retune after v8.4.2.

## Official defaults

| Model | OCR | Interval | Role |
|---|---:|---:|---|
| Fast V1 | 40% | 45ms | Ultra speed-first, lowest latency, minimal polish |
| Fast V2 | 45% | 60ms | Low-latency balanced, cleanup retained |
| Fast IDN | 50% | 75ms | Fast V2-like path with light Indonesian naturalizer |

## Guardrails

- Fast CT2 model path is unchanged.
- Auto / Interval / Freeze semantics are unchanged.
- Heavy NLP/live post-processing remains disabled for Fast live loop.
- OCR 35% is not the default because GFL2 wide-dialog OCR can become too noisy; it can be exposed later as experimental only.

## Reset note

If WebUI still shows older Fast OCR or interval values, the model likely has an autosaved modification. Press **Reset Default** on that model to apply the new built-in v8.4.3 defaults.
