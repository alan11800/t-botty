# Vercel Python Function: /api/webex
import os, json, re, requests
from http.server import BaseHTTPRequestHandler
from datetime import date, timedelta
import re

TOKEN = os.environ["WEBEX_BOT_TOKEN"]
API = "https://webexapis.com/v1"

def business_days_before(d: date, n: int) -> date:
    """
    Return the date that is n business days before d (Mon–Fri only).
    Example: if d is a Monday and n=1 -> previous Friday.
    """
    cur = d
    remaining = n
    while remaining > 0:
        cur = cur - timedelta(days=1)
        if cur.weekday() < 5:  # 0=Mon ... 4=Fri, 5=Sat, 6=Sun
            remaining -= 1
    return cur

def timeline_from(text: str):
    # expect DD/MM/YYYY (kept simple on purpose)
    m = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", text)
    if not m:
        return None
    d, mth, y = map(int, m.groups())
    event = date(y, mth, d)

    # T-3w, T-2w, T-1w are now "business weeks" (15, 10, 5 business days)
    t3  = business_days_before(event, 15).strftime("%d/%m")
    t2  = business_days_before(event, 10).strftime("%d/%m")
    t1  = business_days_before(event, 5).strftime("%d/%m")
    t3d = business_days_before(event, 3).strftime("%d/%m")

    return f"**T3_{t3}** | **T2_{t2}** | **T1_{t1}** | **T3d {t3d}**"

def get_message(mid):
    r = requests.get(f"{API}/messages/{mid}", headers={"Authorization": f"Bearer {TOKEN}"})
    r.raise_for_status(); return r.json()

def post_message(room_id, markdown, parent_id):
    r = requests.post(f"{API}/messages",
        headers={"Authorization": f"Bearer {TOKEN}"},
        json={"roomId": room_id, "markdown": markdown, "parentId": parent_id})
    r.raise_for_status()

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        evt = json.loads(self.rfile.read(n) or b"{}")
        try:
            data = evt.get("data", {})
            msg  = get_message(data["id"])
            # avoid loops
            if (msg.get("personEmail") or "").endswith("@webex.bot"):
                return self._ok("ok")
            text = (msg.get("text") or msg.get("markdown") or "").strip()
            out  = timeline_from(text) or "Send me a date like **21/10/2025**."
            post_message(data["roomId"], out, data["id"])
            return self._ok("ok")
        except Exception as e:
            return self._ok(f"ignored: {e}")

    def _ok(self, s):
        self.send_response(200); self.send_header("Content-Type","text/plain"); self.end_headers()
        self.wfile.write(s.encode())
