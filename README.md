# 粵語 TTS 實驗室 · Cantonese TTS Playground

貼上一段文字，用不同開源 TTS 引擎讀出粵語，即時對比音色、語速與自然度。

A tiny self-hosted web playground for comparing Cantonese text-to-speech engines side by side.

![介面預覽](docs/screenshot.png)

## 為何做這個

GitHub 上「支援粵語」的 TTS 專案不少，但質素、部署成本、粵語處理方式差別很大：有的原生訓練過粵語，有的靠方言指令，有的只是接微軟在線音色，還有的其實只支援普通話。

這個頁面把比較流程固定下來：**同一段文字 → 多個引擎合成 → 順序試聽**，方便快速判斷哪個方案適合自己的場景。

## 功能

- **多引擎並排**：edge-tts、eSpeak NG、瀏覽器 Web Speech，加上可選的 GPT-SoVITS / CosyVoice 3 / OpenAI 兼容服務
- **一鍵全部合成**：逐個引擎排隊合成，任何一個失敗都不影響其他卡片
- **依次試聽**：按順序自動播放，適合做盲聽對比
- **內容哈希快取**：同一段文字 + 同一組參數只合成一次
- **純靜態前端**：HTML/CSS/JS 無構建步驟，後端只有 FastAPI
- **遠端模型適配器**：把自建模型服務接進來，毋須改前端

## 快速開始

需求：Python 3.10+。`espeak-ng`、`ffmpeg` 為可選（前者啟用離線引擎，後者僅用於檢查音頻）。

```bash
git clone https://github.com/leon7786/20261025-Cantonese.git
cd 20261025-Cantonese

python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt

# 可選：離線引擎
sudo apt install espeak-ng        # macOS: brew install espeak-ng

HOST=127.0.0.1 PORT=8000 ./.venv/bin/python -m app
```

打開 <http://127.0.0.1:8000> 即可。也可以直接用 `./run.sh`（自動建立 venv 並安裝依賴）。

## 已接入引擎

| 引擎 | 類型 | 費用 | 粵語來源 | 開箱可用 |
|---|---|---|---|---|
| [edge-tts](https://github.com/rany2/edge-tts) | 在線 | 免費 | 微軟 `zh-HK` 三個音色（曉曼／曉佳／雲龍） | ✅（需聯網） |
| [eSpeak NG](https://github.com/espeak-ng/espeak-ng) | 本地 | 免費 | 內建 `yue` 語音，另有粵拼輸入變體 | 安裝後 ✅ |
| 瀏覽器 Web Speech | 本地 | 免費 | 作業系統 `zh-HK` 語音 | 視系統而定 |
| [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS) | 遠端 | 免費（自架） | `text_lang=yue` + 參考音頻 | 需配置 |
| [CosyVoice 3](https://github.com/FunAudioLLM/CosyVoice) | 遠端 | 免費（自架） | 18+ 中文方言（含粵語） | 需配置 |
| OpenAI 兼容接口 | 遠端 | 需 API Key | 由服務決定 | 需配置 |

頁面按費用分區排列：**免費引擎 → 免費但需自行部署 → 需要 API Key（置底）**。需要 Key 的引擎預設不參與「全部合成」，避免誤觸收費。

## 接入自建模型

複製 `.env.example` 為 `.env` 後填寫，重啟服務生效。未配置的引擎會在頁面上顯示「需配置」，不影響其他引擎。

### GPT-SoVITS

```bash
# 在 GPT-SoVITS 目錄啟動 API
python api_v2.py -a 127.0.0.1 -p 9880 -c GPT_SoVITS/configs/tts_infer.yaml
```

```dotenv
CANTONESE_GPT_SOVITS_URL=http://127.0.0.1:9880
CANTONESE_GPT_SOVITS_REF=/absolute/path/to/reference.wav
CANTONESE_GPT_SOVITS_PROMPT=參考音頻對應的文字（可留空）
```

### CosyVoice 3

```bash
python runtime/python/fastapi/server.py --port 50000 \
  --model_dir pretrained_models/Fun-CosyVoice3-0.5B
```

```dotenv
CANTONESE_COSYVOICE_URL=http://127.0.0.1:50000
CANTONESE_COSYVOICE_SPK=中文女
```

### 其他 OpenAI 兼容服務（如自架 VoxCPM 或網關）

```dotenv
CANTONESE_OPENAI_URL=http://127.0.0.1:9000
CANTONESE_OPENAI_KEY=sk-...
CANTONESE_OPENAI_MODEL=tts-1
CANTONESE_OPENAI_VOICE=alloy
```

## API

| 方法 | 路徑 | 說明 |
|---|---|---|
| `GET` | `/api/health` | 健康檢查 |
| `GET` | `/api/engines?refresh=true` | 引擎清單、可用狀態、音色 |
| `POST` | `/api/tts` | 合成，返回音頻 URL 與耗時 |
| `GET` | `/audio/{name}` | 讀取快取音頻 |

```bash
curl -X POST http://127.0.0.1:8000/api/tts \
  -H 'Content-Type: application/json' \
  -d '{"engine":"edge-tts","text":"你好，我係阿明。","voice":"zh-HK-HiuMaanNeural","rate":0}'
```

```json
{"engine":"edge-tts","voice":"zh-HK-HiuMaanNeural","url":"/audio/5ad8f1541c673891f2a0.mp3",
 "mime":"audio/mpeg","bytes":33984,"ms":1512,"cached":false}
```

錯誤語義：`400` 參數錯、`502` 引擎失敗、`503` 引擎不可用、`504` 合成超時。

## 專案結構

```
app/
  engines/          # 每個專案一個適配器，統一 Engine 介面
    edge.py  espeak.py  gpt_sovits.py  cosyvoice.py  openai_compat.py
  cache.py          # 內容哈希 + 檔案快取
  config.py         # .env 讀取
  main.py           # FastAPI 路由
web/                # 無構建前端（index.html / app.js / styles.css）
scripts/smoke_test.py
docs/
```

新增引擎只需繼承 `app/engines/base.py` 的 `Engine`，實作 `probe()` 與 `synth()`，再註冊到 `app/engines/__init__.py`。

## 粵語 TTS 項目 Star 排行

以下為 2026-10-25 以 GitHub API 抓取的數據，僅列出**官方文檔確認支援粵語**的 TTS 專案：

| # | 項目 | Stars | 粵語支持方式 |
|---|---|---|---|
| 1 | [RVC-Boss/GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS) | 63.7k | `yue` 原生語言代碼，訓練集含粵語 |
| 2 | [OpenBMB/VoxCPM](https://github.com/OpenBMB/VoxCPM) | 40.6k | VoxCPM2 方言列表含粵語 |
| 3 | [FunAudioLLM/CosyVoice](https://github.com/FunAudioLLM/CosyVoice) | 24.1k | CosyVoice 3 覆蓋 18+ 方言（含廣東/粵語） |
| 4 | [k2-fsa/sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) | 15.5k | 官方 `vits-cantonese` ONNX 模型，可端側 |
| 5 | [PaddlePaddle/PaddleSpeech](https://github.com/PaddlePaddle/PaddleSpeech) | 12.7k | `examples/canton/tts3` 粵語配方 |
| 6 | [rany2/edge-tts](https://github.com/rany2/edge-tts) | 12.4k | 微軟 `zh-HK` 音色 |
| 7 | [espeak-ng/espeak-ng](https://github.com/espeak-ng/espeak-ng) | 7.0k | 內建 `yue` 語音 |
| 8 | [OpenMOSS/MOSS-TTS](https://github.com/OpenMOSS/MOSS-TTS) | 4.2k | 31 語言含 `yue` |
| 9 | [Soul-AILab/SoulX-Podcast](https://github.com/Soul-AILab/SoulX-Podcast) | 3.6k | 支援粵語／四川話／河南話播客 |
| 10 | [Edge0-AI/Audio8_TTS](https://github.com/Edge0-AI/Audio8_TTS) | 1.9k | 語言表含粵語 |
| 11 | [hgneng/ekho](https://github.com/hgneng/ekho) | 1.2k | 粵拼驅動的離線引擎 |
| 12 | [stepfun-ai/Step-Audio-EditX](https://github.com/stepfun-ai/Step-Audio-EditX) | 991 | 零樣本克隆支援粵語 |

未列入的高星專案（官方語言表無粵語）：VibeVoice 55.0k、fish-speech 33.4k、index-tts 24.7k、Qwen3-TTS 14.0k、ChatTTS、Spark-TTS、MegaTTS3、F5-TTS、Chatterbox 等。

> Star 數反映熱度，不代表粵語效果。榜上第 6／7／11 名本質是在線服務封裝或傳統合成，音質與神經網絡模型不在同一層級。

## 注意事項

- `edge-tts` 調用微軟在線朗讀服務，需聯網並受其服務條款約束，不適合敏感內容或商用兜底。
- 本專案**不含任何模型權重**，只做調用與對比；離線模型請按各專案說明自行部署。
- 粵語在多數引擎中是「順帶支援」，建議用含懶音、口語詞、中英夾雜的句子實測。
- 合成結果快取在 `.cache/`，可直接刪除。

## License

MIT
