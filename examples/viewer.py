"""Live viewer: RGB and colour-mapped depth side by side (needs opencv-python).

A viewer must always show the NEWEST frame. With RCVHWM=2 the subscriber's
queue is tiny, so if drawing is slower than 30 fps old frames are dropped by
ZeroMQ instead of piling up (which would make the picture lag behind).
Note: ZMQ_CONFLATE would keep only the last message, but it does not support
multipart messages - therefore RCVHWM is used here.
"""

import argparse
import json

import cv2
import numpy as np
import zmq


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--connect", default="tcp://127.0.0.1:5557")
    args = parser.parse_args()

    context = zmq.Context()
    sub = context.socket(zmq.SUB)
    sub.setsockopt(zmq.RCVHWM, 2)
    sub.connect(args.connect)
    sub.setsockopt(zmq.SUBSCRIBE, b"kinect.rgb")
    sub.setsockopt(zmq.SUBSCRIBE, b"kinect.depth")

    rgb = np.zeros((480, 640, 3), np.uint8)
    depth = np.zeros((480, 640, 3), np.uint8)
    try:
        while True:
            topic, meta, data = sub.recv_multipart()
            info = json.loads(meta)
            h, w = info["height"], info["width"]
            if topic == b"kinect.rgb":
                if info["format"] == "jpeg":
                    rgb = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
                else:
                    rgb = cv2.cvtColor(np.frombuffer(data, np.uint8).reshape(h, w, 3), cv2.COLOR_RGB2BGR)
            else:
                raw = np.frombuffer(data, "<u2").reshape(h, w)
                scaled = (np.clip(raw, 400, 1100) - 400) * 255 // 700  # near = dark
                depth = cv2.applyColorMap(scaled.astype(np.uint8), cv2.COLORMAP_JET)
                depth[raw >= 2047] = 0  # invalid pixels black
            cv2.imshow("Kinect v1 via ZeroMQ  (q = quit)", np.hstack([rgb, depth]))
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()
        sub.close(linger=0)
        context.term()


if __name__ == "__main__":
    main()
