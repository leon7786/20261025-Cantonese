# 開發筆記 · 經驗總結

這個專案從「粵語 TTS 排行調研」開始，一路長成「多引擎對比 + 跟讀學習」的兩個頁面。
這裡記錄踩過的坑、量到的數據和做過的取捨，方便之後回頭查。

> 最後更新：2026-10-26

---

## 1. 專案演進

| 階段 | 做了什麼 |
|---|---|
| 調研 | GitHub API 抓 14 個支援粵語的 TTS 專案，按 Star 排序並核實粵語支援 |
| 對比頁 | FastAPI + 無構建前端，同一段文字丟給多引擎 |
| 主題 | 深色 → 淺色（米白紙感 + 青綠主色） |
| 分區 | 免費優先 → 按實測音質分組（推薦 / 基線 / 自建 / 需 Key / 表現較差置底） |
| 引擎 | 3 個 → 10 個（含 3 個 Key-only 雲服務） |
| 跟讀頁 | 14 篇短文、153 段、離線音頻、粵拼注音、逐句點播 |

---

## 2. 引擎實測數據

| 引擎 | 類型 | 實測延遲 | 模型/體積 | 音質 | 備註 |
|---|---|---|---|---|---|
| edge-tts | 在線 | 0.6–1.8s | 微軟 zh-HK | 好 | 粵語只有 3 個音色 |
| gTTS | 在線 | 0.3–0.6s | Google `yue` | 中上 | 只有一個發音人；tld 不換人 |
| canto-tts | 本地 CPU | ~1.4s | 730 MB ONNX | 中上 | 單一 baked voice，見 §5 |
| sherpa-onnx VITS | 本地 CPU | 0.4–0.7s | 108 MB | 中下 | 小模型，字尾偶有吞音 |
| eSpeak NG | 本地 | <50ms | 幾 MB | 差 | 共振峰合成，僅作基線 |
| Ekho | 本地 | <50ms | 13 MB 數據 | 差 | 粵拼詞典，固定語速 |
| Qwen-Audio-3.0-TTS-Plus | 在線 API | 10–15s/句 | 雲端 | 最好 | 見 §3、§4 |
| Google Cloud TTS | 在線 API | 未測 | yue-HK-Standard A–D | 未測 | 只接好接口，等 Key |
| ElevenLabs | 在線 API | 未測 | multilingual v2 | 未測 | 官方語言表有 `yue` |
| cantonese.ai | 在線 API | 未測 | V8.3 | 未測 | 粵語專用，支援粵拼提示 |

結論：**純 CPU 本地跑不出好粵語**。能聽的組合只有 edge-tts / gTTS / canto-tts / Qwen。
CosyVoice2-Yue、GPT-SoVITS、VoxCPM2 這些要 GPU，本機沒有。

---

## 3. 阿里百煉 / Qwen 踩坑記錄

### 3.1 Key 有兩種，端點不通用

| Key 前綴 | 對應端點 | 能用什麼 |
|---|---|---|
| `sk-…` | `dashscope.aliyuncs.com` | 標準按量付費，含語音 |
| `sk-sp-…` | `token-plan.cn-beijing.maas.aliyuncs.com` | Token Plan，含語音（實測可用） |
| `sk-sp-…`（Coding Plan） | `coding.dashscope.aliyuncs.com` | 只有編碼模型，`/audio/speech` 404 |

拿 `sk-sp-` Key 打 `dashscope.aliyuncs.com` 會 `401 InvalidApiKey`，不是 Key 壞，是**端點不對**。
`/compatible-mode/v1/audio/speech` 在 token-plan 域名下返回 `400 url error`，語音只能走 WebSocket。

一句話：**先確認 Key 屬於哪個端點，再談模型。**

### 3.2 語音協議：WebSocket inference

```
wss://…/api-ws/v1/inference
Authorization: Bearer <key>

run-task      {task_group: audio, task: tts, function: SpeechSynthesizer,
               model, parameters:{text_type, voice, format, sample_rate,
                                  volume, rate, pitch, instruction,
                                  word_timestamp_enabled}}
→ task-started
continue-task {input:{text}}
finish-task   {input:{}}
← result-generated（每條後跟一幀 binary 音頻）
← task-finished / task-failed（header.error_message）
```

要點：

- `format` 可選 `pcm` / `wav` / `mp3` / `opus`；選 `pcm` 後自己封 WAV 最穩
- `sample_rate` 可選 8000–48000，預設 22050
- 音色屬模型：3.0-plus 是 `longanlingxin`（女）/ `longanlufeng`（男），不能跨模型混用
- **粵語不在 `language_hints` 裡**，方言靠 `instruction`，官方句式是「请用广东话表达。」
- 文本裡可以直接塞情感/擬聲標籤（`[laughing]` 之類），不用額外參數

### 3.3 字級時間戳：能拿到，但別太信

開 `word_timestamp_enabled: true` 後，`payload.output.sentence.words` 會給每個 token 的
`text / begin_index / end_index / begin_time / end_time`（毫秒）。

坑：

1. **時間戳是均勻估算的**：實測每個字固定約 239ms，不是真實對齊
2. **標點會併進下一個字**：`「，大」` 是一個 token，`begin_time` 是逗號的時間
3. 直接拿「下一個字開始時間」當切點，會把上一個字的尾音切掉（例如「如果唔系，」）

解法見 §4.3。

### 3.4 其他限制

- 單次輸入 600 字（官方），代碼裡按 2000 字擋，實際超過會被 API 拒
- 計費 1.4 元/萬字元，RPM 180
- 一把 `sk-sp-` Key 曾在 `coding` 端點返回「invalid access token or token expired」，
  但同一把 Key 在 `token-plan` 端點完全正常——**同前綴不同套餐，端點必須對**

---

## 4. 跟讀頁：切句與音頻處理

### 4.1 切句規則（`segments_of`）

1. 按「。」「，」「！」切（句號、逗號、感嘆號都切）
2. **不足 4 個字的段**，與下一段合併；最後一段不足 4 字則併回上一段

```python
raw = re.split(r"(?<=[。，！])", text)
```

合併是必要的：否則「咦？」「唉，」這種會變成 0.5 秒的碎片。

### 4.2 粵拼對齊：按字數分配，不要按標點切

粵拼裡頓號「、」也寫成 `,`，直接按逗號切會多出段數（「蝦餃、燒賣、叉燒包」）。
正確做法是：**每段的非標點字數 → 消耗同樣數量的粵拼 token**。

字數統計還要處理兩個特殊情況：

- **引號、書名號、括號**不算字（`“ ”`、`《》`、`（）`）
- **連續英文字母算 1 個**：`Tony` 在粵拼裡是 1 個 token，不能算 4 個字

### 4.3 切點吸附靜音谷（關鍵）

時間戳不準 → 切點偏移 → 尾音被切。解法：

```
在估算切點 ±300ms 內，按 10ms 幀算 RMS，
取能量最低的幀中心作為實際切點
```

效果：「如果唔系，」從 0.95s 變成 1.0s，切點從 26732ms 移到 27027ms，
落在字與字之間的停頓上，兩邊都不切字。

### 4.4 音頻格式

- Qwen 返回 PCM：16-bit、單聲道、24 kHz
- 自己封 WAV 頭，寫入前加 **8ms 淡入淡出**，避免爆音
- 每段驗證：`sum(段長) == 總時長`、`len(cuts) == len(segments) + 1`

---

## 5. canto-tts 多音色：一次推理期 hack

官方 ONNX bundle 只有一個 baked voice，README 也寫明「暫不支援 voice cloning」。

但 runtime 仍然用 `prompt_audio_codes` 作為條件，所以：

1. 用模型自帶的 audio tokenizer（`moss_audio_tokenizer_encode.onnx`）把參考音頻編碼成 codes
2. 合成前把 `_backend._default_voice_codes` 換成新的 codes
3. 得到不同音色

實測（同一句話）：

| 音色 | 參考來源 | F0 | 備註 |
|---|---|---|---|
| 預設 | 模型自帶 | 105 Hz | 穩定 |
| 女聲 | sherpa VITS 生成的粵語 | 205 Hz | 可用 |
| 男聲 | Common Voice 粵語（CC0） | 100 Hz | 音色偏亮 |

坑：

- 用 espeak / pitch-shifted 音頻當參考會產生重複、吞字（ASR 轉出亂碼）
- 合成要加鎖，否則併發切換 codes 會互相污染
- 參考音頻必須 48 kHz 立體聲
- 這是推理期條件切換，不是複刻級克隆

---

## 6. 工程細節

### 6.1 後端

- 引擎統一介面：`probe()` + `synth(text, voice, rate, pitch, api_key, instruction)`
- `probe` 結果快取 60 秒，避免每次開頁都打網絡
- 快取 key 包含 `engine|voice|rate|pitch|instruction|text`——**instruction 一定要算進去**，
  否則粵語和普通話會撞同一份音頻
- Key 只存在瀏覽器 `localStorage`，隨請求傳給本機後端，不落盤、不進快取

### 6.2 FastAPI 靜態檔的坑

`@app.get("/audio/{name}")` 會攔截所有 `/audio/*`，導致靜態目錄裡的
`web/audio/*.wav` 全部 404。解法：課程音頻改放 `/lessons/audio/...`。

### 6.3 `.env`

自製的極簡 loader 只認 `KEY=VALUE`。
如果直接貼純文字（平台名 / Key / 模型名三行），不會被讀到——要先把格式整理好。

### 6.4 前端

- 無構建：`index.html` + `app.js` + `learn.js`，改完刷新即可
- 靜態資源加 `?v=` 版本號，避免瀏覽器快取舊 CSS
- 播放狀態機：`playing / paused / single`，`ended` 事件推進下一句
- 自動播放需要使用者手勢：側欄點擊 → 直接 `play()` 是允許的；刷新後自動播會被瀏覽器擋
- `localStorage` 記住：當前文章、點過的句子、最後位置

### 6.5 Python 3.14 的依賴問題

- `gTTS` 套件 pin 住 `click<8.2`，和 `huggingface_hub>=8.4` 衝突
  → 不用 gTTS 套件，直接打 `translate.google.com/translate_tts`
- `torch` 在 3.14 只能拉到 GPU 版（2GB+），且下載會塞滿 `/tmp`
  → 放棄本地大模型，改用 API 或小模型
- `canto-tts` 的 ONNX 外部數據不支援 HF 快取的 symlink
  → 用 `snapshot_download(..., local_dir=...)` 下載真實檔案

### 6.6 系統依賴

- `espeak-ng`：`apt install espeak-ng`，自帶 `yue`
- `sherpa-onnx`：pip 裝即可，模型首次自動下載 108 MB
- `ekho`：Ubuntu 26.04 沒有套件，需源碼編譯（見 `scripts/install-ekho.sh`）
- `ffmpeg`：只用來檢查音頻和轉檔

---

## 7. 重建流程

```bash
# 1. 環境
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
./.venv/bin/pip install -r requirements-canto.txt   # 可選
./.venv/bin/pip install sherpa-onnx                 # 可選

# 2. 跑起來
HOST=127.0.0.1 PORT=8000 ./.venv/bin/python -m app

# 3. 重建跟讀頁音頻（需要 .env 的百煉 Key）
python scripts/build_lessons.py

# 4. 冒煙測試
python scripts/smoke_test.py
```

`.env` 需要的變數見 `.env.example`；Qwen 最少要
`CANTONESE_DASHSCOPE_KEY` + `CANTONESE_QWEN_WS_URL`。

---

## 8. 檔案地圖

```
app/engines/     每個引擎一個檔案，統一 Engine 介面
web/             前端（index.html 對比頁 / learn.html 跟讀頁）
web/lessons/     跟讀頁的離線音頻與清單
data/articles.json   文章原文 + 粵拼（重建音頻的來源）
scripts/         build_lessons.py / smoke_test.py / mock_qwen_*.py / install-ekho.sh
docs/            截圖與本筆記
```

---

## 9. 已知限制與下一步

- **Qwen 每句 10–15 秒**：跟讀頁靠離線預生成繞過，對比頁仍是即時等
- **粵語音色少**：edge 只有 3 個；Azure 是同一批，所以沒接
- **canto-tts 多音色是實驗性的**：音高/音質有差，咬字仍由同一個聲學模型決定
- **沒有 GPU**：CosyVoice2-Yue / GPT-SoVITS 只能做成自建適配，本機跑不動
- 可做：串流播放（邊生成邊播）、逐字卡拉 OK 高亮、使用者上傳參考音頻解鎖更多音色
