"""Decode captured serial chunks from gateway events.jsonl (run at repo root)."""
import argparse
from dataclasses import asdict
import json
from gateway.protocol import SlipDecoder, atr_unpack, Message


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("log")
    args = parser.parse_args()
    decoders = {"wire_rx": SlipDecoder(), "wire_tx": SlipDecoder()}
    with open(args.log, encoding="utf-8") as stream:
        for line in stream:
            event = json.loads(line)
            if event.get("link") != "serial" or event["event"] not in decoders:
                continue
            for record in decoders[event["event"]].feed(bytes.fromhex(event["hex"])):
                try:
                    test, sequence, payload = atr_unpack(record)
                    print(json.dumps(dict(utc=event["utc"],direction=event["event"],
                        test_id=test,sequence=sequence,message=asdict(Message.unpack(payload)))))
                except ValueError as error:
                    print(json.dumps(dict(utc=event["utc"],error=str(error))))


if __name__ == "__main__":
    main()
