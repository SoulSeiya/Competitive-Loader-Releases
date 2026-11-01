"""Decode/resample off Tk's thread; display one bounded frame on one canvas."""
import json
import queue
import threading
import time
import tkinter as tk


class AnimatedBackground:
    def __init__(self,canvas,item,folder,active):
        self.canvas,self.item,self.folder,self.active=canvas,item,folder,active
        metadata=json.loads((folder/'animation.json').read_text(encoding='utf-8-sig'))
        self.count=metadata['frames'];self.delay=metadata['delay_ms'];self.index=-1
        self.current=None;self.closed=False;self.timer=None;self.enabled=False;self.epoch=0
        self.uploader=None
        self.views=[]
        self.size=(0,0);self.frames=queue.Queue(maxsize=1);self.wake=threading.Event();self.stop=threading.Event()
        self.error=None;self.frames_displayed=0
        self.decode_ms=[];self.display_ms=[]
        self.thread=threading.Thread(target=self.decode,name='BTC background',daemon=True);self.thread.start()
        self.tick()

    def position(self):
        if self.closed:return
        self.canvas.coords(self.item,self.canvas.canvasx(self.canvas.winfo_width()/2),self.canvas.canvasy(self.canvas.winfo_height()/2))
        for view,item in self.views:
            x=self.canvas.winfo_rootx()+self.canvas.winfo_width()/2-view.winfo_rootx()
            y=self.canvas.winfo_rooty()+self.canvas.winfo_height()/2-view.winfo_rooty()
            view.coords(item,view.canvasx(x),view.canvasy(y))

    def add_view(self,canvas,item):
        self.views.append((canvas,item))
        if self.current:canvas.itemconfigure(item,image=self.current)
        self.position()

    def decode(self):
        decoder=None;epoch=-1;frame=0
        try:
            from background_decoder import BackgroundDecoder
            decoder=BackgroundDecoder()
            while not self.stop.is_set():
                if not self.enabled:
                    self.wake.wait(.2);self.wake.clear();continue
                if epoch!=self.epoch:epoch=self.epoch;frame=(self.index+1)%self.count
                started=time.monotonic();size=self.size
                pixels=decoder.render((self.folder/f'frame-{frame:04d}.gif').resolve(),*size)
                if len(self.decode_ms)<100:self.decode_ms.append((time.monotonic()-started)*1000)
                if self.enabled and self.epoch==epoch:
                    try:self.frames.get_nowait()
                    except queue.Empty:pass
                    self.frames.put_nowait((epoch,frame,pixels))
                elapsed=time.monotonic()-started
                advance=max(1,int(elapsed*1000/self.delay));frame=(frame+advance)%self.count
                self.stop.wait(max(.001,self.delay/1000-(time.monotonic()-started)))
        except Exception as exc:self.error=type(exc).__name__
        finally:
            if decoder:decoder.close()

    def tick(self):
        if self.closed:return
        active=bool(self.active()) and not self.error
        size=(max(320,min(2560,self.canvas.winfo_width())),max(240,min(1440,self.canvas.winfo_height())))
        if active!=self.enabled or (active and size!=self.size):
            self.epoch+=1;self.size=size;self.enabled=active;self.wake.set()
        if active:
            try:
                epoch,frame,pixels=self.frames.get_nowait()
                if epoch==self.epoch:
                    displayed=time.monotonic()
                    if self.current is None:
                        from background_photo import BackgroundPhoto
                        self.current=tk.PhotoImage(master=self.canvas)
                        self.uploader=BackgroundPhoto(self.current)
                        self.canvas.itemconfigure(self.item,image=self.current)
                        for view,item in self.views:view.itemconfigure(item,image=self.current)
                    self.uploader.put(pixels)
                    self.index=frame;self.frames_displayed+=1
                    if len(self.display_ms)<100:self.display_ms.append((time.monotonic()-displayed)*1000)
            except queue.Empty:pass
            except (OSError,ValueError,RuntimeError,tk.TclError) as exc:
                # Keep the last valid image if Windows/Tk cannot present a frame.
                self.error=type(exc).__name__;self.enabled=False;self.wake.set()
        self.timer=self.canvas.after(24 if active else 200,self.tick)

    def close(self):
        self.closed=True;self.enabled=False;self.stop.set();self.wake.set()
        if self.timer:
            try:self.canvas.after_cancel(self.timer)
            except tk.TclError:pass
        self.thread.join(timeout=.5)
