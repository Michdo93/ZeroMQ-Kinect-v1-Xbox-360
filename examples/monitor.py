import zmq
c=zmq.Context();s=c.socket(zmq.SUB);s.setsockopt(zmq.SUBSCRIBE,b'kinect.');s.connect('tcp://127.0.0.1:5557');print('Subscribed to kinect.*; Ctrl-C stops')
try:
 while True:
  topic,meta,data=s.recv_multipart();print(topic.decode(),meta.decode(),'payload_bytes=',len(data))
except KeyboardInterrupt:pass
finally:s.close(0);c.term()
