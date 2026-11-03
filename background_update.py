"""One verified staging download at a time; never installs in the background."""
import json
from pathlib import Path
import threading


class BackgroundUpdate:
    def __init__(self, stage):
        self._stage=stage
        self._condition=threading.Condition()
        self._key=None;self._phase='idle';self._path=None;self._error=''

    @staticmethod
    def key(release):
        return json.dumps(release,sort_keys=True,default=str)

    def snapshot(self):
        with self._condition:return {'phase':self._phase,'error':self._error}

    def prepare(self, release):
        release=dict(release);key=self.key(release)
        with self._condition:
            if self._phase=='downloading':return
            if self._key==key and self._phase=='ready' and self._path and Path(self._path).is_file():return
            self._key=key;self._phase='downloading';self._path=None;self._error=''
        def run():
            try:
                path=self._stage(release)
                if not Path(path).is_file():raise OSError('No se encontró el Loader descargado.')
                with self._condition:self._path=path;self._phase='ready'
            except Exception as exc:
                with self._condition:self._error=str(exc);self._phase='error'
            finally:
                with self._condition:self._condition.notify_all()
        threading.Thread(target=run,name='BTC verified update download',daemon=True).start()

    def wait_ready(self, release):
        key=self.key(release)
        while True:
            self.prepare(release)
            with self._condition:
                self._condition.wait_for(lambda:self._phase!='downloading')
                if self._key!=key:continue
                if self._phase!='ready':raise OSError(self._error or 'No se pudo descargar el Loader.')
                return self._path
