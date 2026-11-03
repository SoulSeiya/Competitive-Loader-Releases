"""Bundle the known dependency-free Worker modules for Cloudflare's editor."""
from pathlib import Path
import re
root=Path(__file__).parent
out=[]
for name in ['diagnostics_admin','combat_activity','combat_diagnostics','diagnostics','ranked_recovery','ranked','social','challonge']:
    source=(root/(name+'.mjs')).read_text(encoding='utf-8')
    names=re.findall(r'^export\s+(?:async\s+)?(?:function|class|const)\s+(\w+)',source,re.M)
    source=re.sub(r'^import .*?;\s*\n','',source,flags=re.M)
    source=re.sub(r'^export\s+','',source,flags=re.M)
    out.append('const {'+','.join(names)+'}=(()=>{\n'+source+'\nreturn {'+','.join(names)+'};\n})();\n')
worker=(root/'worker.mjs').read_text(encoding='utf-8')
worker=re.sub(r'^import .*?;\s*\n','',worker,flags=re.M)
(root/'diagnostics-bundle.mjs').write_text('\n'.join(out)+worker,encoding='utf-8')
for name in ['test_diagnostics','test_ranked','test_casual_regression','test_ranked_desync_guard','test_ranked_recovery']:
    source=(root/(name+'.mjs')).read_text(encoding='utf-8').replace("from './worker.mjs'","from './diagnostics-bundle.mjs'")
    (root/(name+'_final_bundle.mjs')).write_text(source,encoding='utf-8')
