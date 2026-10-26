# Our verified software status — 26 October 2026

We tested implementation revision `65f91e5`. Documentation-only updates after this revision do not change the tested code.

| Check | Result | Environment / evidence |
|---|---|---|
| Python protocol, validation, gateway, and API tests | **19 passed** | Local Windows, Python 3.13 |
| Same Python suite in CI | **Passed** | GitHub Actions, Python 3.11 |
| Actual shared C protocol and station state machine | **Passed** | GCC with AddressSanitizer and UndefinedBehaviorSanitizer in CI |
| ESP32 A firmware build | **Passed** | Espressif ESP-IDF v5.5.1 container, target esp32 |
| ESP32 B firmware build | **Passed** | Espressif ESP-IDF v5.5.1 container, target esp32 |
| Browser command and live status flow | **Passed in simulation** | 10 parts, queue 2, production 100 ms, inspection 250 ms, N=3 K=0; 7 PASS, 3 FAIL |
| Documentation relative links | **Passed** | No broken local Markdown links |

We can inspect [the successful CI run](https://github.com/MohamedGeasa/mct431-production-network/actions/runs/40352854792). The Python test environment emitted a third-party Starlette/httpx deprecation warning; all tests passed. The initial inspection build exposed a function-name collision with an internal Espressif Wi-Fi symbol, which we fixed by prefixing our function with `mct_` before this successful run.

The browser run used the same application behaviour before the final session-display fix; we additionally tested that 64-bit session identities are preserved as exact hexadecimal strings in browser-facing evidence.

## What we have not yet verified

We have not flashed physical boards, validated their USB drivers or Wi-Fi connections, run the two-PC hardware demonstration, or collected real annotated Wireshark captures. Only Bluetooth COM ports were present during initial development. We do not claim physical Milestone 1 acceptance until we complete [the hardware checklist](TESTING.md).

The VS Code ESP-IDF extension was installed on the development PC, but a configured local ESP-IDF SDK/toolchain was not established during this work. Firmware compilation was verified in the official Espressif CI container. We follow [DEPLOYMENT.md](DEPLOYMENT.md) to install/select the SDK locally and flash our actual boards.
