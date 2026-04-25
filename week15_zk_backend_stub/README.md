# Week 15 - ZK Backend Stub

Week 15 的目標是把 Week 14 的 constraint artifact 再整理成 backend-ready bundle。

## 執行方式

```bash
python week15_zk_backend_stub/run_zk_backend_stub.py
```

## 輸出

- `results/bundle_index.csv`
- `results/summary.md`
- `results/bundles/*/io_bundle.json`
- `results/bundles/*/verification_hint.json`
- `results/bundles/*/backend_note.json`

## 重要說明

- 這一步仍然不是正式 proof / verify
- 目的是把 witness、public inputs、驗證期望拆開，方便後續接入真實 ZK backend
- 目前環境沒有安裝 `ezkl`，因此 repo 內先完成 stub handoff 格式
