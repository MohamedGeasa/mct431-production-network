# We verify behaviour and preserve evidence

## Automated software checks

From the repository root we run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Our tests exercise CRC and byte-order reference vectors; fragmented SLIP with escaping, noise, and overflow; corrupted records; invalid runtime parameters; complete batches with different queue sizes and relative speeds; capacity reservations; pause/resume/stop; HTTP duplicate/conflict handling; WebSocket status; disconnect faults; stale replies; a lost completion followed by a retry without duplicate execution; and fragmented/coalesced messages through a real local TCP socket.

The portable C test uses the actual firmware protocol and station state machine. On a machine with a C compiler:

```sh
cc -std=c11 -Wall -Wextra -Werror \
  -Ifirmware/components/mct_protocol/include -Ifirmware/components/mct_node/include \
  tests/native/test_node.c firmware/components/mct_protocol/mct_protocol.c \
  firmware/components/mct_node/mct_node.c -o test_node
./test_node
```

GitHub CI runs Python tests, the native C test with sanitizers, and both ESP-IDF v5.5.1 builds. A successful firmware build verifies compilation; it does not prove UART wiring, radio connectivity, timing on the boards, or the examiner's live demonstration.

## Hardware acceptance checklist — to be performed on the boards

We record the date, board model, firmware commit, configuration, observed result, and evidence paths for each check. We leave unchecked items unclaimed.

| Check | Procedure and expected result | Evidence |
|---|---|---|
| Full batch | Fresh session, 10 parts, N=3 K=0: IDs 3,6,9 FAIL; total accepted+rejected=10 | Parts CSV, matching TCP jobs/results, serial records |
| Runtime settings | Set examiner-chosen times and N/K through the UI; observe CONFIG delivery, acceptance, completion | Annotated CONFIG exchanges |
| Producer faster | Production 200 ms, inspection 1000 ms, queue 2; queue fills and production blocks | Status plus production_blocked event |
| Inspector faster | Production 1000 ms, inspection 200 ms; queue stays near empty | Status and event timestamps |
| Queue variations | Repeat with capacity 1 and 8; waiting + reserved never exceeds selected capacity | Run configurations and logs |
| Pause/Resume | Pause during work; existing jobs finish, no new jobs start; Resume continues same IDs/batch | State transitions and request timestamps |
| Stop | Stop mid-batch; current jobs settle, waiting parts discarded, outcome stopped | Stop completion and incomplete counts |
| Duplicate job | Replay an identical valid request in a controlled test; receive cached result and no new work | Same ID, original completion, replay response |
| Invalid command | Send invalid N=0 directly to B in a controlled test; REJECTED code 4 | Rejection exchange |
| Disconnect A | Unplug A during a batch; Fault, no false completion; reconnect then Stop/new batch | Fault and changed boot/session evidence |
| Disconnect B | Remove B's power/network; Fault; old results cannot become new verdicts | TCP interruption and gateway fault |
| Gateway restart | Interrupt the gateway; old batch is abandoned; boards reset after watchdog or manual EN | Separate run/session IDs |
| Two-PC operation | Use the separate operator PC for commands and observe live status | Demonstration and HTTP/WebSocket capture |

The software tests cover several of these fault paths already. We still perform the physical equivalents rather than treating simulation as physical evidence. We do not run the formal Milestone 2 traffic matrix here.

## Wireshark TCP capture

1. We install Wireshark with Npcap on the gateway.
2. We select the adapter carrying B's hotspot traffic. If traffic is missing, we inspect available adapters and confirm B's IP and the gateway route.
3. We capture with filter `tcp port 9000` (or the configured port).
4. We start a batch and save the capture as `.pcapng` within the matching local evidence folder.
5. We use display filter `tcp.port == 9000`, then Follow → TCP Stream. The messages are binary and length-prefixed, as specified in PROTOCOL.md.
6. Optionally we load `tools/wireshark/mct431.lua` into Wireshark's personal Lua plugins folder, restart Wireshark, and inspect named fields with filter `mct431`.
7. We annotate the relevant packets with packet comments: CONFIG parameters, an INSPECT request, its DELIVERED and ACCEPTED responses, and its COMPLETED verdict with the same identifiers. We save comments in pcapng.

We do not call a bare `send()` a delivery or a TCP acknowledgement an inspection completion. Our application events show those distinctions explicitly.

## Serial evidence

`events.jsonl` records actual serial receive/transmit chunks as hex and decoded application lifecycle events. We use the helper to inspect a saved run:

```powershell
.\.venv\Scripts\python.exe tools/decode_serial_log.py evidence/runs/<run>/events.jsonl
```

The helper reconstructs separate receive/transmit streams, verifies CRCs, and prints decoded messages. Boot text and partial chunks are handled by the same SLIP decoder. We preserve the original JSONL as raw evidence and annotate copied excerpts with the matching part and command IDs.

## Interpretation and limitations

We report results from actual tests only. The JSONL timestamps use UTC for chronological records and a monotonic gateway clock for durations. `parts.csv` is a per-part production record, not a formal benchmark CSV. We do not label these runs as throughput or protocol-comparison results.

Very short requested durations can be dominated by transport and scheduler overhead. A disconnected station can finish an already accepted virtual timer before its watchdog expires; the gateway faults the batch and does not reinterpret that delayed result as fresh work. Lost Wi-Fi configuration, serial drivers, hotspot routing, and Windows Firewall must be verified on the physical setup.
