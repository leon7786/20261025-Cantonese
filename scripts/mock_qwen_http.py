#!/usr/bin/env python3
"""Mock DashScope multimodal-generation endpoint for local tests (port 8770).

Text containing "FALLBACK" returns a 400 model error so the client's
HTTP -> WebSocket fallback can be exercised.

    python scripts/mock_qwen_http.py
    CANTONESE_QWEN_HTTP_URL=http://127.0.0.1:8770/api/v1/services/aigc/multimodal-generation/generation
"""
import base64, io, json, math, struct, wave
from http.server import BaseHTTPRequestHandler, HTTPServer

SR = 24000
def wav_b64(seconds=0.5, freq=660):
    n=int(SR*seconds)
    pcm=b"".join(struct.pack("<h", int(9000*math.sin(2*math.pi*freq*i/SR))) for i in range(n))
    buf=io.BytesIO()
    with wave.open(buf,"wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm)
    return base64.b64encode(buf.getvalue()).decode()

class H(BaseHTTPRequestHandler):
    def do_POST(self):
        n=int(self.headers.get("content-length","0")); body=json.loads(self.rfile.read(n) or b"{}")
        text=(body.get("input") or {}).get("text","")
        print("HTTP mock:", body.get("model"), body.get("input"), flush=True)
        if "FALLBACK" in text:
            self.send_response(400); self.send_header("content-type","application/json"); self.end_headers()
            self.wfile.write(json.dumps({"code":"InvalidParameter","message":"model not supported"}).encode())
            return
        self.send_response(200); self.send_header("content-type","application/json"); self.end_headers()
        self.wfile.write(json.dumps({"output":{"audio":{"data":wav_b64()}}}).encode())
    def log_message(self,*a): pass

HTTPServer(("127.0.0.1",8770),H).serve_forever()
