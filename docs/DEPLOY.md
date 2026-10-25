# 部署記錄 · ccantonese-learning.dlfrp.cn

上線地址：**https://ccantonese-learning.dlfrp.cn:10061/**

## 伺服器

| 項目 | 值 |
|---|---|
| 主機 | CT102（Proxmox LXC） |
| 位址 | `192.168.32.232:60026`，`root` + `/root/.ssh/key` |
| 面板 | 1Panel v2.2.5，`http://192.168.32.232:18875/admin12` |
| OpenResty | Docker 容器 `1Panel-openresty-RWra`，**host 網絡** |
| 站點端口 | 10061（SSL） |

## 目錄與服務

| 用途 | 路徑 |
|---|---|
| 後端程式 | `/opt/cantonese-app`（`.venv` 在裡面） |
| 靜態站點根 | `/opt/1panel/www/sites/ccantonese-learning.dlfrp.cn/index` |
| Nginx 站點配置 | `/opt/1panel/www/conf.d/ccantonese-learning.dlfrp.cn.conf` |
| 服務日誌 | `/var/log/cantonese-tts.log` |
| systemd 單元 | `/etc/systemd/system/cantonese-tts.service` |

後端監聽 `127.0.0.1:8100`（8000 被其他程式佔用），由 OpenResty 反代 `/api/` 與 `/audio/`。

```bash
systemctl status cantonese-tts
systemctl restart cantonese-tts
tail -f /var/log/cantonese-tts.log
```

## Nginx 關鍵配置

在站點 conf 的 `server {}` 內追加：

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:8100;   # 容器是 host 網絡，127.0.0.1 即宿主
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_read_timeout 180s;
}
location /audio/ {
    proxy_pass http://127.0.0.1:8100;
    proxy_set_header X-Real-IP $remote_addr;
}
```

改完重載（OpenResty 在容器裡）：

```bash
docker exec 1Panel-openresty-RWra openresty -t
docker exec 1Panel-openresty-RWra openresty -s reload
```

## 更新流程

```bash
# 1. 後端（改了 app/ 或 requirements.txt）
rsync -av --exclude .venv --exclude .cache --exclude .git \
  app/ root@192.168.32.232:/opt/cantonese-app/app/ -e "ssh -p 60026 -i /root/.ssh/key"
ssh ... 'cd /opt/cantonese-app && ./.venv/bin/pip install -q -r requirements.txt && systemctl restart cantonese-tts'

# 2. 前端（改了 web/）
rsync -av web/ root@192.168.32.232:/opt/1panel/www/sites/ccantonese-learning.dlfrp.cn/index/ \
  -e "ssh -p 60026 -i /root/.ssh/key"

# 3. 跟讀頁音頻重建後，同步 web/lessons/ 與 lessons.json 即可（純靜態）
```

## 安全與成本

- Qwen Key 放在伺服器 `/opt/cantonese-app/.env`，頁面不暴露
- `/api/tts` 有 **每 IP 每分鐘 12 次** 的限制（`CANTONESE_RATE_LIMIT`），超限返回 429
- 若要完全關閉伺服器端 Key（只讓訪客自帶 Key），註解掉 `.env` 的
  `CANTONESE_DASHSCOPE_KEY` 並重啟服務
- OpenResty 的 WAF 與 1Panel 登錄入口保持原樣

## 目前部署差異

- 伺服器是 **Python 3.11**，`tarfile.extractall(filter=...)` 需要 3.12+，
  已加 `try/except TypeError` 兼容
- 已安裝 `espeak-ng`；`canto-tts`、`ekho` 未安裝（顯示為不可用）
- `sherpa-onnx` 首次合成會下載 108 MB 模型（已預熱）
- 跟讀頁 14 篇 / 153 段音頻為靜態檔，不經過後端
