# Our working decision notes

We preserve decisions here so we can later explain how our system developed. This is a working record, not the final report.

| Decision | Our reason |
|---|---|
| ESP-IDF and VS Code | We follow the selected toolchain and use explicit ESP-IDF projects rather than Arduino sketches. |
| Windows gateway and separate operator PC | We follow our available setup and retain the assignment's four-device arrangement. |
| Shared C components | We keep framing, validation, and command lifecycle consistent across both boards. |
| Fixed binary messages | We make field offsets, bounds, and framing unambiguous and easy to inspect with a dissector. |
| Central runtime defaults in TOML | We change queue capacity and timing cases without hunting through implementation files. |
| Runtime CONFIG messages | We deliver examiner-assigned timings and rule parameters to the boards without reflashing. |
| Reserved queue slot before production | We prevent an in-flight part from overflowing the waiting queue. |
| One outstanding command per station | We simplify duplicate suppression and make each lifecycle trace easy to follow. |
| Session and boot identities | We reject responses from previous gateway runs and board resets. |
| Finish in-flight work on Pause/Stop | We retain explicit results while giving Pause and Stop different batch outcomes. |
| Public repository, ignored local configuration and captures | We share code and documentation without publishing machine credentials or unreviewed packet captures. |
| Explicit simulation label | We can test workflow early while keeping software evidence distinct from the live hardware demonstration. |

We will add actual observations, hardware problems, and justified changes as we test. We will not backfill invented experimental findings.
