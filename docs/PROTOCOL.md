# We define messages before interpreting success

All multibyte binary integers are **unsigned big-endian**. We serialize fields explicitly; we never send a native C struct with padding.

## Application message: 36 bytes

| Offset | Bytes | Field | Meaning |
|---:|---:|---|---|
| 0 | 1 | version | 1 |
| 1 | 1 | kind | COMMAND=1, DELIVERED=2, ACCEPTED=3, COMPLETED=4, REJECTED=5, HELLO=6, PING=7 |
| 2 | 1 | operation | BIND=1, CONFIG=2, PRODUCE=3, INSPECT=4; HELLO/PING use 0 |
| 3 | 1 | station | A=1, B=2 |
| 4 | 8 | session | Random nonzero gateway-process session |
| 12 | 4 | command_id | Increasing nonzero identifier per station/session; HELLO/PING use 0 |
| 16 | 4 | part_id | Stable identity through production, queue, inspection, and result; control messages use 0 |
| 20 | 4 | arg0 | Duration in CONFIG; explicit result/error in COMPLETED/REJECTED |
| 24 | 4 | arg1 | Reject modulus N in B's CONFIG |
| 28 | 4 | arg2 | Reject offset K in B's CONFIG |
| 32 | 4 | boot | Nonzero station boot nonce, learned from HELLO |

The command identity is the tuple `(session, station, command_id)`. The same tuple is echoed in every lifecycle response and retry. Part IDs increase across batches within the gateway session. The full identity across restarts includes the session.

DELIVERED confirms that a complete, decodable application message reached the station. ACCEPTED confirms semantic validation and willingness to execute. COMPLETED contains an explicit result. A corrupt serial frame fails CRC and gets no application acknowledgement; the gateway detects the missing response through its timeout. Local `send()` success is never logged as application delivery or completion.

## Operation semantics

| Operation | Request | Completion |
|---|---|---|
| BIND | Expected station boot and new session; only an unbound station or its existing session is allowed | OK=0 |
| CONFIG to A | arg0 = production duration ms | OK=0 after applying validated configuration |
| CONFIG to B | arg0 = inspection duration ms, arg1=N, arg2=K | OK=0 after applying validated configuration |
| PRODUCE to A | Unique nonzero part_id | OK=0 after the production timer finishes |
| INSPECT to B | Same part_id received from production | PASS=1 or FAIL=2 after B computes `(part_id + K) % N == 0` |

REJECTED arg0 codes: 1 bad station/session/boot binding; 2 old ID or changed request under an existing ID; 3 station busy; 4 invalid operation/parameters or missing configuration.

For HELLO, arg0 is busy (0/1), arg1 is the last accepted command ID, and boot is the current boot nonce. Its session is 0 until binding. PING keeps a bound station's gateway watchdog alive only when station, session, and boot match.

Limits: duration 1–60000 ms, N 1–1000000, K 0–1000000; gateway target 1–10000 and queue capacity 1–1024. B computes the rule with a 64-bit sum to avoid overflow when adding K to the part ID.

## USB serial: ATR inside SLIP

We use UART0 at **115200 baud, 8 data bits, no parity, 1 stop bit, no flow control**.

| ATR field | Bytes | Milestone 1 value |
|---|---:|---|
| test_id | 2 | 1, application traffic |
| seq | 4 | Per-sender frame sequence, starts at 0 and wraps modulo 2^32 |
| payload_len | 2 | 36 |
| payload | 36 | Application message above |
| crc16 | 2 | CRC over header + payload |

An unescaped record is 46 bytes. We use **CRC-16/CCITT-FALSE**: polynomial 0x1021, initial value 0xFFFF, no reflection, xorout 0. The reference string `123456789` produces 0x29B1. The assignment names the CRC family; this document fixes its parameters for interoperability.

SLIP wraps the record with END=0xC0. Within a record, 0xC0 becomes `DB DC` and 0xDB becomes `DB DD`. We reject invalid escapes, oversized frames, bad lengths, unsupported versions, and CRC mismatches. We tolerate boot text before frame boundaries and incremental reads. Retries preserve the application command ID but receive a new frame sequence number.

The fixed benchmark payload pattern and sizes in the assignment belong to Milestone 2. Milestone 1 uses the ATR envelope with a 36-byte command/event payload. We do not claim this is the formal benchmark harness.

## TCP inspection link

ESP32 B listens on TCP port 9000. Every message is:

`uint16 length (=36) | 36-byte application message`

We handle partial reads and multiple messages in one stream. An invalid prefix closes the connection. TCP provides transport ordering and error recovery, while our application messages provide job acceptance and completion. The TCP application payload does not add an ATR envelope or CRC in Milestone 1; only USB serial requires those here.

## Retries and age

We allow one outstanding request per station and at most `max_attempts` transmissions (default 3). Each attempt's completion deadline is:

`ack_timeout_s + requested_work_duration_s + completion_grace_s`

The default control-command deadline is 4 seconds; a 1200 ms inspection gets 5.2 seconds. The setting named `ack_timeout_s` contributes the transport/acceptance allowance to this combined deadline; we do not run a separate acceptance-only timer. We continue heartbeat traffic during long jobs. After a lost completion, a retry retrieves the cached result rather than restarting work.

## HTTP operator API

`POST /api/commands` with JSON:

```json
{"cmd_id":"b157129a-37cd-4abd-ab46-2f7a52b6ef51","action":"start","config":{"target_parts":10,"queue_capacity":2,"production_ms":500,"inspection_ms":1000,"reject_modulus":3,"reject_offset":0}}
```

For `pause`, `resume`, or `stop`, we omit `config`. A new accepted request returns HTTP 202 and `{cmd_id, phase:"accepted"}`. We obtain the final result with `GET /api/commands/<cmd_id>`. A terminal phase is `completed` or `failed`. Invalid syntax/settings return 400, identifier/content conflicts return 409, and an oversized body returns 413. `GET /api/status` provides a snapshot; `/ws` pushes snapshots and recent events four times per second.

Operator UUIDs and binary station IDs occupy different namespaces because Start is a workflow command that creates distinct CONFIG/PRODUCE/INSPECT operations. We preserve each existing identifier within its own exchange; retries never invent replacements.
