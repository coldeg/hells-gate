"""Isolated headless browser helper for local UI checks; never logs credentials."""
import base64
import json
import os
import subprocess
import shutil
import tempfile
import time
import urllib.request
from pathlib import Path
import websocket


class Browser:
    def __enter__(self):
        paths=[Path(os.environ.get('PROGRAMFILES','C:/Program Files'))/'Google/Chrome/Application/chrome.exe',
               Path(os.environ.get('PROGRAMFILES(X86)','C:/Program Files (x86)'))/'Microsoft/Edge/Application/msedge.exe']
        paths += [Path(value) for value in [os.environ.get('HELLS_GATE_BROWSER')] + [shutil.which(name) for name in ('google-chrome','chromium','microsoft-edge','chrome')] if value]
        paths.append(Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'))
        browser=next((p for p in paths if p.is_file()), None)
        if browser is None:raise RuntimeError('Install Chrome/Edge or set HELLS_GATE_BROWSER to its executable')
        profile=Path(tempfile.mkdtemp(prefix='hells_gate_card_'))
        self.process=subprocess.Popen([str(browser),'--headless=new','--disable-gpu','--no-first-run',
            '--disable-background-networking','--disable-extensions','--remote-debugging-port=0',
            '--user-data-dir='+str(profile),'about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        self.connection=None;self.sequence=0;self.errors=[]
        try:
            deadline=time.monotonic()+25
            while not (profile/'DevToolsActivePort').exists():
                if self.process.poll() is not None:raise RuntimeError('Browser startup failed')
                if time.monotonic()>deadline:raise RuntimeError('Browser startup timeout')
                time.sleep(.2)
            port=(profile/'DevToolsActivePort').read_text().splitlines()[0]
            with urllib.request.urlopen('http://127.0.0.1:'+port+'/json/list',timeout=5) as response:
                target=next(t for t in json.load(response) if t['type']=='page')
            self.connection=websocket.create_connection(target['webSocketDebuggerUrl'],timeout=15,suppress_origin=True)
            self.command('Runtime.enable');self.command('Page.enable')
            return self
        except Exception:
            self.__exit__(None,None,None)
            raise

    def __exit__(self,*_):
        if self.connection:self.connection.close()
        if self.process.poll() is None:
            self.process.terminate();self.process.wait(timeout=10)

    def command(self,method,params=None):
        self.sequence+=1
        self.connection.send(json.dumps({'id':self.sequence,'method':method,'params':params or {}}))
        while True:
            message=json.loads(self.connection.recv())
            if message.get('method')=='Runtime.exceptionThrown':self.errors.append(message['params']['exceptionDetails'].get('text','JS error'))
            if message.get('id')==self.sequence:
                if 'error' in message:raise RuntimeError(message['error'])
                return message.get('result',{})

    def js(self,expression):
        result=self.command('Runtime.evaluate',{'expression':expression,'returnByValue':True,'awaitPromise':True})
        if result.get('exceptionDetails'):raise RuntimeError(result['exceptionDetails'])
        return result.get('result',{}).get('value')

    def open(self,path):
        self.command('Page.navigate',{'url':Path(path).as_uri()})
        deadline=time.monotonic()+10
        while not self.js("document.readyState==='complete'"):
            if time.monotonic()>deadline:raise RuntimeError('Page load timeout')
            time.sleep(.1)

    def viewport(self,w,h):
        self.command('Emulation.setDeviceMetricsOverride',{'width':w,'height':h,'deviceScaleFactor':1,'mobile':False})

    def screenshot(self,path):
        raw=self.command('Page.captureScreenshot',{'format':'png','captureBeyondViewport':False})
        Path(path).write_bytes(base64.b64decode(raw['data']))
