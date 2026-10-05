# zk-verifiable-dp-fl

可驗證差分隱私聯邦學習（VDP-FL）研究原型：client 以零知識證明展示 update 經過 clipping，並使用秘密且綁定情境的 randomness 加入離散噪聲；server 只聚合 proof、context 與 replay policy 都通過的更新。

[![Reproducibility matrix](https://github.com/ChiJiun/zk-verifiable-dp-fl/actions/workflows/reproducibility-matrix.yml/badge.svg)](https://github.com/ChiJiun/zk-verifiable-dp-fl/actions/workflows/reproducibility-matrix.yml)

## 目前能主張什麼

| 有證據支持 | 不能由目前結果推出 |
|---|---|
| Actual Halo2 circuit 已整合 setup-bound secret、commit-before-challenge context、Poseidon PRG、canonical centered-binomial sampler、clipping 與 additive-noise relation | 任意維度、任意 participation／rounds 的統一 DP 保證 |
| 固定 `d=4, k=16`、10 rounds、replacement-client profile 下，`epsilon <= 28.840669` at `delta=1e-5` | 385–1,991 維實驗也具有相同 epsilon，或 `epsilon=28.84` 已具強實務隱私 |
| 3 clients × 10 rounds × 5 seeds 的 150 份逐更新 proof 通過，模型鏈可從磁碟重驗 | 更新確實由指定資料與 optimizer 產生，或能阻止任意 poisoning |
| 高維 EZKL constraint cost、K=50／R=20 scaling 與 bounded-poisoning robust aggregation 已量測 | Production 部署效能；1,000-proof workload 仍是明示外推 |

最重要的負面結果也保留：public seed 的舊機制為 `epsilon = infinity`；合法 clipping 範圍內的 300/300 惡意更新會通過 proof gate。詳見[威脅模型](docs/research/threat-model.md)與[主張—證據對照](docs/research/claim-evidence-map.md)。

## Repository 結構

```text
.
├── experiments/                 # 35 個研究單元，依索引閱讀
├── docs/
│   ├── nstc/                    # 結案草稿、摘要與送件 checklist
│   ├── publication/             # 投稿強化報告、roadmap、舊稿來源
│   ├── research/                # 威脅模型、架構、主張—證據對照
│   ├── governance/              # AI 協助等研究治理說明
│   └── archive/                 # 歷史計畫與進度文件
├── scripts/check_repository.py  # CI repository hygiene 檢查
├── Dockerfile                   # 核心 accountant + Halo2 重現環境
└── requirements*.txt
```

- [實驗索引](experiments/README.md)
- [文件索引](docs/README.md)
- [NSTC 長版草稿](docs/nstc/report-draft.md)
- [最新投稿強化報告](docs/publication/strengthening-report.md)

## 核心重現

需求：Python 3.12、Rust stable。Python 3.13 不是 CI 的驗證版本。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-core.txt

python scripts/check_repository.py
python -m unittest discover -s experiments/discrete_noise_accounting -p "test*.py" -v
cargo test --release --manifest-path experiments/halo2_verifiable_randomness/Cargo.toml
python -m unittest discover -s experiments/actual_multiround_halo2 -p "test*.py" -v
```

完整 ML／EZKL 實驗另安裝 `requirements.txt`，再依各實驗 README 執行。UCI Adult 原始資料、衍生 NumPy arrays、`*.key` 與 `*.srs` 不再版控；相關 pipeline 會重新下載或產生它們。

Docker 只包核心 privacy accountant 與 Halo2 circuit，以避免把完整 PyTorch／EZKL toolchain 誤稱為已驗證容器：

```powershell
docker build -t zk-verifiable-dp-fl-core .
docker run --rm zk-verifiable-dp-fl-core
```

## 研究與發布治理

- [AI 協助揭露](docs/governance/ai-assistance.md)已提供可直接採用的文字與口試自查。
- Repository 尚未選定開源授權；在加入正式 `LICENSE` 前，請勿假設程式或資料可被再散布。這項法律選擇需由作者決定。
- 目前最合適定位是 NSTC 結案成果與範圍清楚的 workshop／arXiv systems-security prototype；full paper 仍需形式化 soundness／zero-knowledge／adaptive composition、selective abort／collusion、高維 hidden randomness 與真實 client dataset。

主要技術依據：[Zcash Halo2](https://github.com/zcash/halo2)、[EZKL](https://github.com/zkonduit/ezkl)、[Koskela et al. exact PLD accounting](https://proceedings.mlr.press/v130/koskela21a.html)、[cpSGD binomial mechanism](https://arxiv.org/abs/1805.10559)。
