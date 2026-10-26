# We map Milestone 1 requirements to implementation and evidence

| Requirement | Implementation | Verification / remaining work |
|---|---|---|
| A ↔ gateway USB serial, SLIP/ATR/CRC/sequence | `mct_protocol`, production firmware, `SerialTransport` | Codec tests; physical serial capture pending |
| B ↔ gateway custom TCP with length prefix | inspection `tcp_link.c`, `TcpTransport` | Socket framing tests, firmware build; physical capture pending |
| Unique parts, bounded queue, completion counts | `Controller` | Batch and capacity integration tests; physical batch pending |
| Runtime inspection rule on B | shared C node, B CONFIG/INSPECT | Native C rule tests; examiner configuration demonstration pending |
| Runtime production and inspection durations | CONFIG messages and browser controls | Validation and integration tests; hardware timing checks pending |
| Idle/Running/Paused/Fault | controller and architecture diagram | Pause/resume/stop and disconnect tests |
| HTTP Start/Pause/Resume/Stop, WebSocket status | FastAPI and browser interface | API/WebSocket tests; two-PC demonstration pending |
| Separate delivery/acceptance/completion | three response kinds and evidence events | Native C and gateway lifecycle tests |
| IDs, timeouts, bounded retries, duplicate suppression | station client and C node high-water mark/cache | Lost completion retry test and C duplicate tests |
| Disconnection and stale data | heartbeat, boot/session validation, Fault | Software disconnect/stale tests; physical interruption pending |
| Source and configuration | repository folders and local config template | Repository review |
| Setup/test instructions and diagrams | README and docs | Physical reproducibility check pending |
| Message specification | PROTOCOL.md | Cross-language golden vector test |
| Raw evidence and annotations | evidence logger, decode helper, Wireshark dissector | Real CSV/logs/captures to be collected |
| Contributions and individual explanation | CONTRIBUTIONS.md | Team completion and rehearsal pending |

Formal benchmarking, comparative plots, authenticated MQTT, protocol migration, and the full benchmark matrix belong to Milestone 2. This repository does not claim they have been implemented.
