import json
import pytest
from delta_lab.research import parameter_grid,walk_forward,metrics
from delta_lab.reporting import save_run
from delta_lab.storage import Store
from test_engine import config,rows,run


def test_report_reproducibility(tmp_path):
    data=rows([(100,100,99,100),(102,104,102,103)])
    r=run(data)
    folder,saved=save_run(r,{'BTCUSD':data},Store(tmp_path/'data'),tmp_path/'reports')
    assert (folder/'BTCUSD-input.parquet').exists()
    assert saved['manifest']['snapshots']['BTCUSD']['sha256']
    assert json.loads((folder/'result.json').read_text())['metrics']==metrics(r)
    assert (folder/'events.csv').exists()


def test_walkforward_boundaries():
    data=rows([(100,101,99,100)]*180)
    candidates=parameter_grid(config(),{'relative_volume':[1.5,1.8]})
    folds=walk_forward(candidates,{'BTCUSD':data},60,30,10)
    assert len(folds)==3
    for f in folds: assert f['train_end']<f['test_start']<f['test_end']
    assert all(a['test_end']<=b['test_start'] for a,b in zip(folds,folds[1:]))
    assert all(f['status']=='no training trades; no selection' for f in folds)
    with pytest.raises(ValueError): parameter_grid(config(),{'relative_volume':list(range(101))})


def test_walkforward_evaluates_selected_configuration():
    prices=([100,99,98,97,96,95,94,93,92,91,90,120,125,130,135,100]*20)
    data=rows([(p,p+1,p-1,p) for p in prices])
    c=config(rsi_length=2,volume_lookback=2,relative_volume=.5)
    folds=walk_forward([c],{'BTCUSD':data},90,60,10)
    evaluated=[f for f in folds if f['status']=='evaluated']
    assert evaluated and all(f['training']['trades']>0 for f in evaluated)
    for f in evaluated:
        assert all(t['entry_time']>=f['test_start'] for t in f['test_result']['trades'])
        assert f['selected_config']==c.model_dump()


def test_saved_run_reproduction(tmp_path,monkeypatch):
    import delta_lab.__main__ as cli
    from delta_lab.engine import Engine
    c=config()
    data={'BTCUSD':rows([(100,101,99,100)]*30)}
    r=Engine(c).run(data)
    folder,saved=save_run(r,data,Store(tmp_path/'data'),tmp_path/'reports')
    monkeypatch.setattr(cli,'ROOT',tmp_path)
    assert cli.verify_run(folder/'result.json')==metrics(r)
    snapshot=folder/'BTCUSD-input.parquet'; snapshot.write_bytes(b'tampered')
    with pytest.raises(ValueError,match='hash mismatch'): cli.verify_run(folder/'result.json')
