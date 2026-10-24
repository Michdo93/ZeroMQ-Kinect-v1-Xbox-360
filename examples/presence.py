"""Presence detector: reduces 18 MB/s of depth data to a handful of events.

Subscribes ONLY to kinect.depth, measures the distance of the nearest object
in the central region of the image and publishes a small JSON event when the
zone changes:

    presence.zone   {"zone": "near" | "medium" | "far" | "empty", "distance_m": 0.93}

Typical use: a smart-home rule ("someone is standing in front of the mirror
-> light on") subscribes to presence.* instead of processing raw depth frames.
"""

import argparse
import json
import time

import numpy as np
import zmq


def raw_to_meters(raw: np.ndarray) -> np.ndarray:
    """Approximation for the Kinect v1 11-bit raw value (2047 = no data)."""
    return 0.1236 * np.tan(raw / 2842.5 + 1.1863)


ZONES = [("near", 1.0), ("medium", 2.0), ("far", float("inf"))]
HYSTERESIS_M = 0.1  # a zone change needs 10 cm beyond the border -> no flapping


def zone_for(distance: float, current: str = None) -> str:
    if np.isnan(distance):
        return "empty"
    lower = 0.0
    for name, upper in ZONES:
        if name == current and lower - HYSTERESIS_M <= distance < upper + HYSTERESIS_M:
            return current  # stay in the current zone inside the tolerance band
        lower = upper
    return next(name for name, upper in ZONES if distance < upper)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--connect", default="tcp://127.0.0.1:5557")
    parser.add_argument("--bind", default="tcp://*:5559")
    args = parser.parse_args()

    context = zmq.Context()
    sub = context.socket(zmq.SUB)
    sub.setsockopt(zmq.RCVHWM, 4)
    sub.connect(args.connect)
    sub.setsockopt(zmq.SUBSCRIBE, b"kinect.depth")
    pub = context.socket(zmq.PUB)
    pub.bind(args.bind)
    print(f"Presence detector: in {args.connect}, events out {args.bind}")

    last_zone = None
    try:
        while True:
            _, meta, data = sub.recv_multipart()
            info = json.loads(meta)
            raw = np.frombuffer(data, "<u2").reshape(info["height"], info["width"])
            roi = raw[120:360, 160:480]  # centre of the image
            valid = roi[roi < 2047]
            # 2nd percentile instead of minimum -> robust against single noisy pixels
            distance = float(raw_to_meters(np.percentile(valid, 2))) if valid.size > 500 else float("nan")
            zone = zone_for(distance, last_zone)
            if zone != last_zone:
                event = {"zone": zone, "distance_m": None if np.isnan(distance) else round(distance, 2),
                         "t_pub_us": time.time_ns() // 1000}
                pub.send_multipart([b"presence.zone", json.dumps(event).encode()])
                print("presence.zone", event)
                last_zone = zone
    except KeyboardInterrupt:
        pass
    finally:
        sub.close(linger=0)
        pub.close(linger=0)
        context.term()


if __name__ == "__main__":
    main()
