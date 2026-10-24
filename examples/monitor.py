"""Prints message rate, bandwidth and latency per Kinect stream once a second."""

import argparse
import collections
import json
import time

import zmq


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--connect", default="tcp://127.0.0.1:5557")
    parser.add_argument("--topic", default="kinect.", help="e.g. kinect.depth")
    args = parser.parse_args()

    context = zmq.Context()
    sub = context.socket(zmq.SUB)
    sub.connect(args.connect)
    sub.setsockopt_string(zmq.SUBSCRIBE, args.topic)

    count, size, lat = collections.Counter(), collections.Counter(), collections.defaultdict(list)
    start = time.time()
    try:
        while True:
            topic, meta, data = sub.recv_multipart(copy=False)  # zero-copy frames
            name = bytes(topic.buffer).decode()
            info = json.loads(bytes(meta.buffer))
            count[name] += 1
            size[name] += len(data.buffer)
            lat[name].append(time.time_ns() // 1000 - info["t_pub_us"])
            if name == "kinect.status":
                print("STATUS", info)
            if time.time() - start >= 1.0:
                for n in sorted(count):
                    l = sorted(lat[n])
                    print(f"{n:<14} {count[n]:4d} msg/s {size[n] / 2**20:7.2f} MiB/s  "
                          f"latency median {l[len(l) // 2] / 1000:6.2f} ms")
                print("-" * 62)
                count.clear(); size.clear(); lat.clear()
                start = time.time()
    except KeyboardInterrupt:
        pass
    finally:
        sub.close(linger=0)
        context.term()


if __name__ == "__main__":
    main()
