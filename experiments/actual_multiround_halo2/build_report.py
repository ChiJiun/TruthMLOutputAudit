"""Build the figure and Chinese research note from completed raw artifacts."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import t


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir",type=Path,default=Path(__file__).parent/'results_roundtrip')
    args = parser.parse_args()
    directory = args.results_dir.resolve()
    config = json.loads((directory/'config.json').read_text())
    summary = json.loads((directory/'summary.json').read_text())
    runs = [json.loads((directory/f'seed_{seed}'/'run.json').read_text()) for seed in config['seeds']]
    privacy_path = Path(__file__).parent/'privacy_results'/'boundary.json'
    privacy = json.loads(privacy_path.read_text())
    rows = json.loads((directory/'seed_measurements.json').read_text())
    n = len(runs)
    rounds = np.arange(1,config['rounds']+1)
    def trajectory(field):
        values = np.array([[r[field] for r in run['trajectory']] for run in runs])
        ci = t.ppf(.975,n-1)*values.std(axis=0,ddof=1)/np.sqrt(n) if n>1 else np.zeros(values.shape[1])
        return values.mean(axis=0),ci
    fig, axes = plt.subplots(1,3,figsize=(14,4.3),layout='constrained')
    for field,label,color in [('proof_gated_accuracy','Verified noisy FL','#2563eb'),
                              ('quantized_no_noise_accuracy','Quantized, no noise','#475569')]:
        mean,ci = trajectory(field)
        axes[0].plot(rounds,mean,label=label,color=color,marker='o',markersize=3)
        axes[0].fill_between(rounds,np.clip(mean-ci,0,1),np.clip(mean+ci,0,1),color=color,alpha=.13)
    axes[0].set(xlabel='Round',ylabel='Synthetic test accuracy',ylim=(0,1),title='Training with actual proofs')
    axes[0].legend(fontsize=8)
    x = np.arange(n)
    axes[1].bar(x-.2,[r['prove_mean_seconds'] for r in rows],width=.4,label='Prove',color='#2563eb')
    axes[1].bar(x+.2,[r['verify_mean_seconds'] for r in rows],width=.4,label='Verify',color='#14b8a6')
    axes[1].set(xticks=x,xticklabels=config['seeds'],xlabel='Dataset seed / independent secret set',ylabel='Seconds per update',title='Actual cost, keys reused within run')
    axes[1].legend(fontsize=8)
    labels = ['Replay','Client','Round','Model','Update','Proof','Retry']
    names = ['duplicate_submission','client_swap','round_swap','model_swap','noisy_update_tamper','corrupt_proof','retry_after_failure']
    counts = [sum(p['attack']==a and p['gate']!='accepted' for run in runs for p in run['probes']) for a in names]
    axes[2].barh(labels,counts,color='#14b8a6')
    axes[2].set(xlabel='Rejected actual-proof probes',title='State and cryptographic rejection')
    for i,count in enumerate(counts): axes[2].text(count*.97,i,str(count),ha='right',va='center',fontsize=8)
    for ax in axes:
        ax.spines[['top','right']].set_visible(False)
        ax.grid(axis='y',alpha=.15)
        ax.set_axisbelow(True)
    fig.suptitle(f"Four-parameter prototype | {n} seeds x {config['clients']} clients x {config['rounds']} rounds",fontsize=13)
    fig.savefig(directory/'experiment.png',dpi=180)
    plt.close(fig)
    metrics = summary['metrics']
    def metric(field):
        m=metrics[field]
        return f"{m['mean']:.4f} ± {m['ci95_half_width']:.4f}"
    def budget_table():
        return '\n'.join(f"| {r['dimension']} | {r['rounds']} | {r['k']} | {r['support_floor']:.6g} | "
                         + (f"{r['basic_composition_epsilon']:.6f}" if r['basic_composition_epsilon'] is not None else '此 δ 下不可用')+' |' for r in privacy)
    branch_url = 'https://github.com/ChiJiun/zk-verifiable-dp-fl/tree/main/experiments/actual_multiround_halo2'
    ci_path = directory/'ci_evidence.json'
    ci_text = '此結果目錄尚未保存對應的 CI 證據。'
    if ci_path.exists():
        ci = json.loads(ci_path.read_text())
        ci_text = f"相關程式 commit {ci['tested_source_commit']} 的 [GitHub CI]({ci['url']}) 已在 Windows／Linux 通過；每個環境另完成 2 clients × 2 rounds、4 份 actual proofs、4 份磁碟重驗與 28 個拒絕 probes。它是乾淨環境的小型重現，與本機 150 份正式矩陣分開計數。"
    note = f'''# VDP-FL 實驗紀錄：逐更新 Halo2 多輪整合與隱私邊界

更新日期：{datetime.now().astimezone().date().isoformat()}

> 本文由實際完成的結果自動整理，可直接貼入 HackMD。線上同步狀態：尚未寫入；本輪瀏覽器工具因無法確認目前網址而停止。

## 一、這次為什麼要做

先前已證明固定四維秘密隨機性 circuit 可以運作；大型 FL 訓練與 proof 成本主要分開量測。因此本次選擇維持四維、直接讓本地訓練產生每輪更新，每份更新都產生 proof、驗證後才聚合，再把結果交給下一輪。

與過去的差異：本次主矩陣的 {summary['actual_proofs']} 份 proof 全部實際產生，整條模型鏈也從磁碟重新驗證。這仍是合成資料的小型原型，沒有增加 production 或高維隱私保證。

## 二、實驗設計

| 項目 | 設定 |
|---|---|
| Seeds | {config['seeds']}，全部保留 |
| Clients × rounds | {config['clients']} × {config['rounds']}／seed |
| 資料 | 公開合成二元資料；每 client 64 筆，test 512 筆；client 特徵位移 |
| 模型 | 三個特徵權重＋bias，共四參數 logistic regression |
| 本地訓練 | 每輪兩次 full-batch gradient steps，learning rate 0.5 |
| 量化 | 更新除以 0.1 後四捨五入，逐座標限制為 -1／0／1，C²=4 |
| 噪聲 | Halo2 內 k=16 centered-binomial sampler；秘密、salt、challenge 使用 OS CSPRNG |
| Context | client、round、精確 model digest、nonce、challenge、commitments |
| 金鑰 | 每個 seeded run setup 一次，供該 run 全部 proofs 重用 |
| 統計 | 每條完整 seeded trajectory 為一個樣本；表中 ± 為 95% t CI 半寬 |

「真實 proof」是已完成密碼學的證明生成與驗證；「model chain」是重新計算每輪平均更新，確認下一輪的模型與 proof 綁定的模型一致。

對照 A 使用同一資料／初始化、不加噪聲的量化訓練；對照 B 把完全相同 noisy updates 直接聚合，檢查驗證流程是否改變誠實結果。B 是算術一致性檢查，沒有假稱為獨立訓練或效能 benchmark。

## 三、實際結果

| 指標 | 實測 |
|---|---:|
| 實際產生且通過的 proofs | {summary['actual_proofs']}/{summary['actual_proofs']} |
| 從磁碟重新驗證 | {summary['disk_reverified_proofs']}/{summary['actual_proofs']} |
| Unique proof hashes | {summary['unique_proof_hashes']} |
| 完整 model chains | {n}/{n} |
| 負面 probes 拒絕 | {summary['negative_probes_rejected']}/{summary['negative_probes']} |
| Proof bytes 合計 | {summary['proof_bytes_total']:,} |
| 每 update prove 秒 | {metric('prove_mean_seconds')} |
| 每 update verify 秒 | {metric('verify_mean_seconds')} |
| 每 trajectory wall 秒 | {metric('wall_seconds')} |
| 每 trajectory peak RSS MiB | {metric('peak_rss_mib')} |
| 每 trajectory keygen 秒 | {metric('keygen_seconds')} |
| Noisy proof-gated final accuracy | {metric('proof_gated_final_accuracy')} |
| Quantized no-noise final accuracy | {metric('quantized_no_noise_final_accuracy')} |

Wall time 包含訓練、proof、負面 probes、儲存與 setup，但不含 Rust 編譯以及另一次磁碟重驗。這兩項各有獨立執行／紀錄。RSS 是 process sampling，非硬體 profiler。合成資料 accuracy 僅作描述，不宣稱五個 seeds 證明泛化或達到統計顯著。

每個 proof 測七種情境：重播、client swap、round swap、model swap、noisy update 篡改、proof bytes 損壞、失敗後重試。重播的原始 proof 仍可通過密碼學驗證，必須由 server ticket 狀態拒絕；其餘 statement 篡改在真正的 verifier 中失敗。Probes 使用原 proof 與獨立 ticket 分支，不是七組完整惡意訓練軌跡。三個額外磁碟負面檢查（模型鏈、公開更新、proof bytes）也全部拒絕。

所有 honest rounds 中，gate 與相同 noisy updates 的直接聚合差異均為 0。

{ci_text}

## 四、隱私參數延伸分析

這次額外用精確有理數計算有限支撐的失配機率，並用 70 位 Decimal 計算逐座標隱私損失的保守基本組合上界。基本組合把各次 ε／δ 相加，可作較保守的適應性分析起點。數值程式並非經形式驗證的區間算術。

| 假設維度 | 輪數 | k | 獨立最壞位移支撐 δ floor | 基本組合 ε 上界 |
|---:|---:|---:|---:|---:|
{budget_table()}

原 PLD accountant 的 28.840669 保留為既有固定 profile 計算；本次基本組合給出較鬆上界，不能把兩個數字的差異說成實測隱私惡化。要把緊的 PLD 數字用到依賴先前模型的多輪訓練，仍須檢查 dominating-pair 與適應性組合證明。

385／1,991 維列是「每座標仍允許 ±1、noise k=16、20 輪」的假設延伸；其 δ floor 已超過 10⁻⁵，所以該延伸不能在此 δ 下取得有限 ε。現有 production_scaling 的量化範圍與 noise unit 不同，不能把這張表直接當成那些模型的 accountant。

本次沒有宣稱完整 transcript 的 DP：commitments、ZK proof、時間與額外診斷的共同洩漏，以及 PRF、commitment hiding、ZK simulation、有限域取 bits 的誤差轉換，仍需安全證明審查。公開合成資料的 clean-control 指標不應直接搬到私有訓練資料上公開。

組合理論來源：[Dwork & Roth, §3.5 / Appendix B](https://www.cis.upenn.edu/~aaroth/Papers/privacybook.pdf)。

## 五、過程中遇到的問題

初次 pilot 的 30 份 proof 即時驗證成功，但模型從 JSON 讀回後，一個數值由 -6.938893903907228e-17 變為 -6.938893903907227e-17，導致精確模型鏈核對失敗。

處理：啟用 serde_json float_roundtrip，加入 bit-for-bit serialization regression test。修正後同一批 pilot 的 30 份 proof／模型鏈重驗成功，再用全新 OS 隨機材料重新跑正式 {n}-seed 矩陣。沒有放寬 model hash 比對容差，也沒有刪掉失敗紀錄。

## 六、這次可以得出的結論

固定四參數、{config['clients']} clients、{config['rounds']} rounds 的設定中，本地訓練、秘密噪聲電路、逐更新 actual proof、accepted-only aggregation 與下一輪模型綁定可以完整串接，且保存後可以獨立重驗。這補上了原先單次 Halo2 展示與分離式 FL 成本量測之間的實作證據。

目前還沒有證明本地訓練來源正確、任意 poisoning 防禦、私有資料完整 transcript 的 DP 或高維 production 成本。下一步優先做自然 client 資料的同規格實驗，以及 commitment／PRF／適應性 composition 的第三方審查；再依資源擴大逐更新 proof 數量。

## 七、重現方式與證據

```powershell
python -m unittest discover -s experiments/actual_multiround_halo2 -p "test*.py" -v
cargo test --release --manifest-path experiments/halo2_verifiable_randomness/Cargo.toml
python experiments/actual_multiround_halo2/run_experiment.py --output-dir experiments/actual_multiround_halo2/my-run
python experiments/actual_multiround_halo2/privacy_boundary.py --output-dir experiments/actual_multiround_halo2/my-privacy
```

使用新的輸出資料夾以保留本次原始結果。OS-random secrets 讓 proof bytes 與 noisy accuracy 不會與上次完全相同；應核對流程、矩陣完整性與驗證結果。

證據：[實驗目錄與重現說明]({branch_url})；results_roundtrip/summary.json、seed_*/run.json、seed_*/proofs/、disk_verification.json、config.json、hardware_manifest.json。圖表為 results_roundtrip/experiment.png。正式資料與 pilot 分開保存。
'''
    (directory/'report_zh.md').write_text(note,encoding='utf-8')
    (Path(__file__).parent/'hackmd_update.md').write_text(note,encoding='utf-8')
    manifest = {}
    for path in sorted(directory.rglob('*')):
        if path.is_file() and path.name != 'artifact_sha256.json':
            manifest[str(path.relative_to(directory)).replace('\\','/')] = hashlib.sha256(path.read_bytes()).hexdigest()
    (directory/'artifact_sha256.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(directory/'report_zh.md')


if __name__ == '__main__':
    main()
