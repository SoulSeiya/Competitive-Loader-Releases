import traceback,json,sys
from pathlib import Path
from rising_service import ServiceClient,DEFAULT_ROOM_SERVICE
result={}
try:
 c=ServiceClient(DEFAULT_ROOM_SERVICE)
 result['rooms']=c.send('list',kind='casual')
except Exception:result['error']=traceback.format_exc()
Path(sys.executable).with_suffix('.diagnostic.json').write_text(json.dumps(result),encoding='utf-8')
