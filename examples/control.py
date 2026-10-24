"""Control client (REQ -> REP tcp://127.0.0.1:5558).

    python examples/control.py status
    python examples/control.py brightness 25
    python examples/control.py tilt 10
    python examples/control.py led blink_green
"""

import argparse

import zmq


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["status", "brightness", "tilt", "led"])
    parser.add_argument("value", nargs="?")
    parser.add_argument("--connect", default="tcp://127.0.0.1:5558")
    args = parser.parse_args()

    request = {"command": "get_status" if args.command == "status" else args.command, "value": args.value}
    context = zmq.Context()
    req = context.socket(zmq.REQ)
    req.setsockopt(zmq.RCVTIMEO, 2000)
    req.setsockopt(zmq.LINGER, 0)
    req.connect(args.connect)
    try:
        req.send_json(request)
        print(req.recv_json())
    except zmq.Again:
        print("No answer - is kinect_bridge.py running?")
    finally:
        req.close()
        context.term()


if __name__ == "__main__":
    main()
