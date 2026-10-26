# We preserve evidence without inventing results

Gateway runs are saved under `runs/` with a timestamp and an explicit `simulation` or `hardware` suffix. These generated folders are ignored by Git so a public push does not accidentally publish packet captures, network details, or large raw logs.

Each run contains:

- `events.jsonl`: configuration, state changes, command events, faults, and serial/TCP wire bytes with gateway timestamps.
- `parts.csv`: completed inspection records with batch, part, verdict, and job IDs.

We add our actual Wireshark `.pcapng` captures and annotations to the matching physical run folder. After reviewing them, we can package them for the milestone submission. We do not fabricate captures or use simulated output as physical evidence.

We record the firmware/Git commit and board details in a short `run-notes.md` beside each captured run. The final report will refer to those real observations.
