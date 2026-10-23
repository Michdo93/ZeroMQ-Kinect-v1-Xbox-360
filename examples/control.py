import argparse,json,zmq
p=argparse.ArgumentParser();p.add_argument('command',choices=['brightness','tilt','led']);p.add_argument('value',type=float);a=p.parse_args()
c=zmq.Context();s=c.socket(zmq.PUSH);s.connect('tcp://127.0.0.1:5558');s.send_string(json.dumps({'command':a.command,'value':a.value}));s.close();c.term();print('Control command queued')
