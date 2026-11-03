from pathlib import Path
from streamlit.testing.v1 import AppTest

ROOT=Path(__file__).resolve().parents[1]


def test_every_empty_dashboard_page_renders():
    app=AppTest.from_file(str(ROOT/'app.py')).run(timeout=20)
    assert not app.exception
    for page in ['Market Data','Strategy Configuration','Backtest Runner','Trade Replay','Loss Diagnosis','Strategy Comparison','Walk-Forward Research','Reports','Overview']:
        app.sidebar.radio[0].set_value(page).run(timeout=20)
        assert not app.exception, f'{page}: {app.exception}'


def test_pages_with_simulated_result():
    from test_engine import rows,run,config
    data=rows([(100,100,99,100),(102,104,102,103),(103,106,102,105)])
    result=run(data)
    app=AppTest.from_file(str(ROOT/'app.py'))
    app.session_state['result']=result
    app.session_state['run_data']={'BTCUSD':data}
    app.session_state['config']=config()
    app.run(timeout=20)
    assert not app.exception
    for page in ['Trade Replay','Loss Diagnosis','Strategy Comparison','Walk-Forward Research','Reports']:
        app.sidebar.radio[0].set_value(page).run(timeout=20)
        assert not app.exception, f'{page}: {app.exception}'
