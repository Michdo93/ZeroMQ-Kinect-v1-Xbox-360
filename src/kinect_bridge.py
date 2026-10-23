import argparse,json,queue,threading,time
import numpy as np
import sounddevice as sd
import zmq
import freenect
OUT=queue.Queue(maxsize=100)
CFG={'brightness':0,'tilt':0,'led':0}
def emit(topic,meta,data=b''):
 try:OUT.put_nowait((topic,json.dumps(meta,separators=(',',':')).encode(),data))
 except queue.Full:pass
def main():
 p=argparse.ArgumentParser();p.add_argument('--audio-device',type=int,default=None);p.add_argument('--bind',default='tcp://*:5557');p.add_argument('--control',default='tcp://127.0.0.1:5558');a=p.parse_args()
 ctx=zmq.Context();pub=ctx.socket(zmq.PUB);pub.setsockopt(zmq.SNDHWM,50);pub.bind(a.bind);ctl=ctx.socket(zmq.PULL);ctl.bind(a.control);poll=zmq.Poller();poll.register(ctl,zmq.POLLIN)
 def video(dev,frame,ts):
  rgb=np.array(frame,copy=True); bright=int(CFG['brightness'])
  if bright:rgb=np.clip(rgb.astype(np.int16)+bright,0,255).astype(np.uint8)
  emit('kinect.color.rgb',{'schema':'kinect.color.v1','width':rgb.shape[1],'height':rgb.shape[0],'format':'RGB24','brightness_offset':bright,'timestamp':int(ts)},rgb.tobytes())
 def depth(dev,frame,ts):
  arr=np.asarray(frame,dtype='<u2').copy()
  emit('kinect.depth.u16',{'schema':'kinect.depth.v1','width':arr.shape[1],'height':arr.shape[0],'format':'depth11-uint16-le','timestamp':int(ts)},arr.tobytes())
 def audio_callback(indata,frames,time_info,status):
  if status:pass
  emit('kinect.audio.pcm',{'schema':'kinect.audio.v1','sample_rate':16000,'channels':indata.shape[1],'format':'PCM16LE'},indata.copy().tobytes())
 def body(dev,context):
  if dict(poll.poll(0)).get(ctl,0)&zmq.POLLIN:
   try:
    m=json.loads(ctl.recv_string())
    if m.get('command')=='brightness':
     CFG['brightness']=max(-100,min(100,int(m['value'])));emit('kinect.status',{'brightness_offset':CFG['brightness']})
    elif m.get('command')=='tilt':
     CFG['tilt']=max(-30,min(30,float(m['value'])));freenect.set_tilt_degs(dev,CFG['tilt'])
    elif m.get('command')=='led':
     CFG['led']=int(m['value']);freenect.set_led(dev,CFG['led'])
   except Exception as e:print('Control error:',e)
  try:
   while True:
    t,j,b=OUT.get_nowait();pub.send_multipart([t.encode(),j,b])
  except queue.Empty:pass
 stream=None
 try:
  stream=sd.InputStream(device=a.audio_device,samplerate=16000,channels=1,dtype='int16',blocksize=1600,callback=audio_callback)
  stream.start();print('Streaming RGB/depth via libfreenect; mic via ALSA. Ctrl-C to stop.')
  freenect.runloop(video=video,depth=depth,body=body)
 except KeyboardInterrupt:pass
 except Exception as e:print('Capture error:',e)
 finally:
  if stream:stream.stop();stream.close()
  ctl.close(0);pub.close(0);ctx.term()
if __name__=='__main__':main()
