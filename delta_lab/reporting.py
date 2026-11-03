from __future__ import annotations
import hashlib,importlib.metadata,json,platform,uuid
from datetime import datetime,timezone
from pathlib import Path
import polars as pl
from .storage import ROOT,atomic_json
from .research import metrics


def save_run(result,data,store,root=ROOT/'reports'):
    root=Path(root); root.mkdir(parents=True,exist_ok=True)
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:8]
    folder=root/run_id; folder.mkdir()
    # Immutable exact input copies allow reproduction even after incremental store updates.
    snapshots={}
    for sym,rows in sorted(data.items()):
        store.directory(sym,'3m') # validate path component
        path=folder/f'{sym}-input.parquet'
        pl.DataFrame(rows).write_parquet(path,compression='zstd')
        snapshots[sym]={'file':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                        'store_sha256':store.snapshot(sym,'3m')}
    result={**result,'metrics':metrics(result),'manifest':{'snapshots':snapshots,
            'software':{p:importlib.metadata.version(p) for p in ['polars','duckdb','pydantic','streamlit','plotly']},
            'python':platform.python_version(),
            'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'delta_lab').glob('*.py'))},
            'installed_packages':{d.metadata['Name']:d.version for d in importlib.metadata.distributions() if d.metadata['Name']},'created_utc':datetime.now(timezone.utc).isoformat(),
            'config_sha256':hashlib.sha256(json.dumps(result['config'],sort_keys=True).encode()).hexdigest()}}
    atomic_json(folder/'result.json',result)
    for key in ('trades','events','equity'):
        rows=result[key]
        if rows:
            # Nested event detail is encoded to preserve all fields without losing mixed schemas.
            if key=='events':
                pl.DataFrame({'time':[r['time'] for r in rows],'symbol':[r['symbol'] for r in rows],
                              'event':[r['event'] for r in rows],'detail_json':[json.dumps(r) for r in rows]}).write_csv(folder/'events.csv')
            else: pl.DataFrame(rows,infer_schema_length=None).write_csv(folder/f'{key}.csv')
    return folder,result


def load_run(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))
