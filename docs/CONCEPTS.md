# We learn the terms through one part's journey

We begin with part 7. We want A to produce it, the gateway to hold it if B is busy, and B to return a reliable verdict. Each concept solves a problem along that journey.

| Term | What we mean |
|---|---|
| ESP-IDF | Espressif's C/C++ development framework, libraries, and build tools for ESP chips |
| Firmware | The program we compile and flash onto an ESP32 |
| Flashing | Writing compiled firmware into the board's flash memory |
| Gateway | Our Windows coordinator between the wired station, wireless station, and operator |
| Protocol | Agreed rules for representing and exchanging information |
| UART / USB serial | The board's UART byte stream carried through its onboard USB bridge to a Windows COM port |
| TCP | An ordered reliable byte stream while a network connection works; it does not define application message boundaries |
| Framing | How we recover individual messages from a stream of bytes |
| SLIP | Delimiter-and-escape framing for the serial records |
| Length prefix | A size field before each TCP message so we know how many bytes belong to it |
| Payload | The useful data carried inside a record or frame |
| ATR | Application Test Record: a header, payload, and CRC; used as the serial envelope here |
| Big-endian | Storing the most significant byte first so both sides agree on integer representation |
| CRC | A checksum designed to detect accidental corruption; it is not authentication |
| HTTP | Request/response communication used for our operator commands |
| WebSocket | A persistent connection for pushing status updates to the operator browser |
| Queue / FIFO | A waiting list processed in first-in, first-out order |
| Backpressure | Slowing or stopping new production when downstream capacity is full |
| State machine | Rules defining our state and which events change it |
| Deterministic rule | The same part ID and parameters always give the same verdict |
| Acknowledgement | A message confirming a precisely defined stage of an exchange |
| Timeout | A deadline beyond which we stop waiting as if everything were still normal |
| Bounded retry | Trying the same request again a limited number of times |
| Duplicate suppression | Recognizing already accepted work and preventing it from executing again |
| Heartbeat | Periodic evidence that a device is still communicating |
| Stale data | A result that is too late or belongs to an old session, boot, or job |
| Watchdog | A timer that triggers recovery if expected activity stops |
| Wireshark capture | A recorded network exchange we inspect to prove what was sent and received |

We deliver the inspection request for part 7. That says the bytes arrived. B then validates it and accepts the job. Only after the configured inspection time does B compute PASS or FAIL and report completion. We keep those three events separate because the network cannot tell us that application work has finished.

If a reply is lost, we resend the same request with the same ID. B recognizes it and returns its known status/result. If we gave the retry a new ID, we would accidentally ask for new work. If B reboots, its boot nonce changes, so we abandon the old batch rather than treating a stale reply as fresh evidence.

We use these definitions in the code and demonstration. We will later turn the decisions and observations into our final report, using "we" throughout.
