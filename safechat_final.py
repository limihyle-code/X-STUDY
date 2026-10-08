#!/usr/bin/env python3
"""
Limi — Premium Verified Video Chat
Aadhaar 18+ | Gender premium locks | Levels | Front/Back camera
"""

import io, zipfile, datetime, base64, re, time, uuid, random, string
from xml.etree import ElementTree as ET
from flask import Flask, request, render_template_string, redirect, session, jsonify

app = Flask(__name__)
app.secret_key = "limi-premium-2026-v2"
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

WAITING, ROOMS, GROUPS, REPORTS, BANNED = [], {}, {}, {}, set()
CREDIT_POOL = 0  # demo pool from subscriptions

def t(key):
    L = {
        "en": {"home":"Home","world":"World","client":"Client","chat":"Chat","favourite":"Favourite",
               "account":"My Account","logout":"Logout","verified":"Verified 18+","likes":"Likes",
               "save":"Save","upload_photo":"Upload Photo","select_lang":"Language","coming":"Coming Soon",
               "tap":"Tap to start video chatting","online":"online","girl":"Girl","guy":"Guy",
               "random":"Random","prefs":"Preferences","age":"Age Range","lang_f":"Language","apply":"Apply",
               "finding":"Connecting you to someone special...","connected":"Connected","next":"Next",
               "report":"Report","block":"Block","end":"End","all_g":"All Genders","group":"Add Group",
               "create_g":"Create Group","join_g":"Join with Code","max10":"Up to 10 people",
               "chat_soon":"Real chat coming soon","premium":"Go Premium","flip":"Flip Cam"},
        "hi": {"home":"होम","world":"वर्ल्ड","client":"क्लाइंट","chat":"चैट","favourite":"पसंदीदा",
               "account":"मेरा अकाउंट","logout":"लॉगआउट","verified":"वेरिफाइड 18+","likes":"लाइक्स",
               "save":"सेव","upload_photo":"फोटो अपलोड","select_lang":"भाषा","coming":"जल्द आ रहा है",
               "tap":"वीडियो चैट शुरू करें","online":"ऑनलाइन","girl":"लड़की","guy":"लड़का",
               "random":"रैंडम","prefs":"फ़िल्टर","age":"उम्र","lang_f":"भाषा","apply":"लागू करें",
               "finding":"आपको किसी खास से जोड़ रहे हैं...","connected":"कनेक्टेड","next":"अगला",
               "report":"रिपोर्ट","block":"ब्लॉक","end":"बंद","all_g":"सभी","group":"ग्रुप",
               "create_g":"ग्रुप बनाएं","join_g":"कोड से जॉइन","max10":"अधिकतम 10 लोग",
               "chat_soon":"रियल चैट जल्द","premium":"प्रीमियम लें","flip":"कैमरा बदलें"}
    }
    return L.get(session.get("lang","en"), L["en"]).get(key, key)

def is_premium():
    exp = session.get("premium_until")
    if not exp: return False
    try: return datetime.datetime.fromisoformat(exp) > datetime.datetime.utcnow()
    except: return False

def is_girl():
    return (session.get("gender") or "") == "F"

def can_use_filter(want):
    """Boys: only BOTH(random) free. Girls: all free. Premium boys: all."""
    if is_girl() or is_premium(): return True
    return want in ("BOTH", "RANDOM", "")

CSS = """
<style>
*{box-sizing:border-box;margin:0;padding:0;font-family:system-ui,-apple-system,sans-serif}
body{background:linear-gradient(180deg,#1a1050 0%,#0f0a2e 45%,#0a0618 100%);min-height:100vh;color:#eee;padding-bottom:64px;overflow-x:hidden}
.topbar{display:flex;justify-content:space-between;align-items:center;padding:12px 16px;background:rgba(0,0,0,0.15);border-bottom:1px solid rgba(255,255,255,0.05);z-index:20}
.logo{font-size:1.2rem;font-weight:700;background:linear-gradient(90deg,#c4b5fd,#60a5fa);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.profile-box{display:flex;align-items:center;gap:8px}
.avatar{width:36px;height:36px;border-radius:50%;background:linear-gradient(135deg,#7c3aed,#2563eb);display:flex;align-items:center;justify-content:center;font-weight:700;overflow:hidden;font-size:0.95rem}
.avatar img{width:100%;height:100%;object-fit:cover}
.pname{font-weight:600;font-size:0.85rem}.pstatus{font-size:0.65rem;color:#4ade80}
.logout-btn{color:#f87171;font-size:0.72rem;text-decoration:none}
.page{padding:0;min-height:calc(100vh - 130px)}
.center{text-align:center;padding-top:40px;color:#888}
.bottom-nav{position:fixed;bottom:0;left:0;right:0;height:60px;background:rgba(12,8,35,0.97);border-top:1px solid rgba(255,255,255,0.07);display:flex;justify-content:space-around;align-items:center;z-index:100}
.nav-item{display:flex;flex-direction:column;align-items:center;text-decoration:none;color:#666;font-size:0.6rem;width:16%;padding:3px 0}
.nav-item.active{color:#a78bfa}
.nav-item svg{width:20px;height:20px;margin-bottom:2px;fill:currentColor}
.card{background:rgba(255,255,255,0.06);border-radius:16px;padding:16px;margin:12px;border:1px solid rgba(255,255,255,0.08)}
label{display:block;margin:8px 0 4px;font-size:0.84rem;color:#a5b4fc}
input,select{width:100%;padding:11px;border-radius:10px;border:1px solid #444;background:rgba(0,0,0,0.3);color:#fff;font-size:0.9rem}
.btn{border:none;border-radius:12px;padding:12px 18px;font-weight:600;font-size:0.92rem;cursor:pointer;color:#fff}
.btn-primary{background:linear-gradient(90deg,#7c3aed,#2563eb);width:100%}
.btn-gold{background:linear-gradient(90deg,#b45309,#f59e0b);width:100%}
.success{background:#065f46;color:#fff;padding:12px;border-radius:10px;text-align:center;margin:10px}
.error{background:#7f1d1d;color:#fff;padding:10px;border-radius:8px;margin:10px;font-size:0.9rem}
.info{background:rgba(99,102,241,0.12);border-left:3px solid #818cf8;padding:10px;border-radius:0 8px 8px 0;margin:10px;font-size:0.84rem;color:#c7d2fe}
.splash{position:fixed;inset:0;background:linear-gradient(160deg,#1e1b4b,#312e81,#4c1d95);display:flex;flex-direction:column;align-items:center;justify-content:center;z-index:999;animation:fadeOut 0.6s ease 2.2s forwards}
.splash-logo{font-size:3.2rem;font-weight:800;letter-spacing:2px;background:linear-gradient(90deg,#e9d5ff,#a5b4fc,#67e8f9);-webkit-background-clip:text;-webkit-text-fill-color:transparent;animation:pulseLogo 1.5s ease infinite}
.splash-sub{margin-top:12px;color:rgba(255,255,255,0.6);font-size:0.95rem;letter-spacing:1px}
.splash-bar{width:120px;height:3px;background:rgba(255,255,255,0.15);border-radius:4px;margin-top:28px;overflow:hidden}
.splash-bar-in{height:100%;width:0;background:linear-gradient(90deg,#a78bfa,#60a5fa);animation:loadBar 2s ease forwards}
@keyframes pulseLogo{0%,100%{transform:scale(1)}50%{transform:scale(1.04)}}
@keyframes loadBar{to{width:100%}}
@keyframes fadeOut{to{opacity:0;visibility:hidden}}
.home-hero{text-align:center;padding:28px 16px 10px}
.home-hello{font-size:1.4rem;font-weight:700;margin-bottom:4px}
.home-sub{color:#94a3b8;font-size:0.88rem;margin-bottom:14px}
.home-badge{display:inline-block;background:rgba(74,222,128,0.15);color:#4ade80;padding:5px 14px;border-radius:20px;font-size:0.78rem;font-weight:600;margin:0 4px}
.home-badge.gold{background:rgba(245,158,11,0.2);color:#fbbf24}
.home-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;padding:12px}
.home-tile{background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:18px 12px;text-align:center;text-decoration:none;color:#eee}
.home-tile .emoji{font-size:1.8rem;margin-bottom:6px}
.home-tile .t{font-weight:600;font-size:0.9rem}
.home-tile .s{font-size:0.72rem;color:#94a3b8;margin-top:3px}
.home-tip{margin:14px 12px;padding:14px;background:rgba(167,139,250,0.1);border-radius:14px;font-size:0.84rem;color:#c4b5fd;line-height:1.45}
.level-bar{height:6px;background:rgba(255,255,255,0.1);border-radius:4px;margin-top:8px;overflow:hidden}
.level-fill{height:100%;background:linear-gradient(90deg,#a78bfa,#60a5fa);border-radius:4px}
.start-screen{display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:calc(100vh - 200px);padding:16px;text-align:center}
.tap-text{font-size:1.3rem;font-weight:600;margin-bottom:8px;color:#fff}
.online-dot{display:inline-block;width:8px;height:8px;background:#22c55e;border-radius:50%;margin-right:6px;animation:pulse 1.5s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.4}}
.online-count{font-size:0.92rem;color:#94a3b8;margin-bottom:18px}
.connect-wrap{position:relative;width:130px;height:130px;margin:12px auto 30px;cursor:pointer}
.connect-core{position:absolute;inset:38px;border-radius:50%;background:rgba(167,139,250,0.28);border:2px solid rgba(167,139,250,0.7)}
.connect-ring{position:absolute;inset:0;border-radius:50%;border:2px solid rgba(167,139,250,0.5);animation:ripple 2s ease-out infinite}
.connect-ring:nth-child(2){animation-delay:0.55s}
.connect-ring:nth-child(3){animation-delay:1.1s}
@keyframes ripple{0%{transform:scale(0.4);opacity:0.85}100%{transform:scale(1.2);opacity:0}}
.bottom-filters{position:absolute;bottom:68px;left:0;right:0;padding:0 12px;display:flex;flex-direction:column;gap:8px}
.filter-row{display:flex;gap:8px}
.filter-chip{flex:1;background:rgba(255,255,255,0.07);border:1px solid rgba(255,255,255,0.1);border-radius:14px;padding:11px 10px;text-align:left;cursor:pointer;color:#e2e8f0;position:relative}
.filter-chip .title{font-size:0.86rem;font-weight:600}
.filter-chip .sub{font-size:0.7rem;color:#94a3b8;margin-top:2px}
.filter-chip .lock{position:absolute;top:8px;right:8px;font-size:0.75rem}
.group-chip{background:rgba(167,139,250,0.12);border:1px solid rgba(167,139,250,0.35);border-radius:14px;padding:12px;text-align:center;cursor:pointer;color:#e9d5ff;font-weight:600}
.popup-bg{position:fixed;inset:0;background:rgba(0,0,0,0.55);z-index:200;display:none;align-items:flex-end;justify-content:center}
.popup{background:#1a1a2e;border-radius:20px 20px 0 0;padding:18px;width:100%;max-width:420px;max-height:80vh;overflow-y:auto}
.popup h3{text-align:center;margin-bottom:12px;font-size:1rem}
.popup-opt{padding:13px;border-radius:12px;margin-bottom:7px;background:rgba(255,255,255,0.05);text-align:center;cursor:pointer;font-weight:500}
.popup-opt:active{background:rgba(167,139,250,0.25);color:#a78bfa}
.code-box{font-size:1.6rem;font-weight:700;letter-spacing:4px;text-align:center;padding:14px;background:rgba(0,0,0,0.3);border-radius:12px;margin:12px 0}
.premium-sheet{text-align:center}
.premium-sheet .price{font-size:2rem;font-weight:800;color:#fbbf24;margin:8px 0}
.premium-sheet .perks{text-align:left;font-size:0.88rem;color:#c4b5fd;line-height:1.6;margin:12px 0}
.call-screen{position:fixed;inset:0;background:#0a0618;z-index:50;display:none;flex-direction:column}
#remoteVideo{flex:1;width:100%;object-fit:cover;background:#111}
#localVideo{position:absolute;right:12px;top:52px;width:100px;height:140px;border-radius:12px;object-fit:cover;border:2px solid rgba(255,255,255,0.25);background:#222;z-index:60}
.call-top{position:absolute;top:0;left:0;right:0;padding:12px 14px;display:flex;justify-content:space-between;align-items:center;z-index:70;background:linear-gradient(to bottom,rgba(0,0,0,0.5),transparent)}
.call-status{font-size:0.9rem;color:#fff;text-shadow:0 1px 3px #000}
.menu-btn{width:36px;height:36px;border-radius:50%;background:rgba(0,0,0,0.4);border:none;color:#fff;font-size:1.2rem;cursor:pointer}
.menu-dropdown{position:absolute;top:48px;right:14px;background:#1e1e32;border-radius:12px;padding:6px 0;min-width:140px;display:none;z-index:80;box-shadow:0 8px 24px rgba(0,0,0,0.4)}
.menu-dropdown button{display:block;width:100%;padding:12px 16px;background:none;border:none;color:#eee;text-align:left;font-size:0.9rem;cursor:pointer}
.call-bottom{position:absolute;bottom:0;left:0;right:0;padding:16px;display:flex;justify-content:center;gap:14px;z-index:70;background:linear-gradient(to top,rgba(0,0,0,0.55),transparent)}
.ctrl-btn{width:54px;height:54px;border-radius:50%;border:none;font-size:0.7rem;font-weight:600;color:#fff;cursor:pointer;display:flex;align-items:center;justify-content:center;flex-direction:column}
.ctrl-next{background:rgba(255,255,255,0.15)}
.ctrl-end{background:#dc2626}
.ctrl-flip{background:rgba(96,165,250,0.35)}
.finding-overlay{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;background:radial-gradient(circle at center,#1e1b4b 0%,#0a0618 70%);z-index:55}
.finding-rings{position:relative;width:160px;height:160px;margin-bottom:24px}
.finding-rings .r{position:absolute;inset:0;border-radius:50%;border:2px solid rgba(167,139,250,0.4);animation:findRipple 2.2s ease-out infinite}
.finding-rings .r:nth-child(2){animation-delay:0.5s}
.finding-rings .r:nth-child(3){animation-delay:1s}
.finding-rings .core{position:absolute;inset:50px;border-radius:50%;background:linear-gradient(135deg,rgba(167,139,250,0.4),rgba(96,165,250,0.3));display:flex;align-items:center;justify-content:center;font-size:1.8rem}
@keyframes findRipple{0%{transform:scale(0.35);opacity:0.9}100%{transform:scale(1.25);opacity:0}}
.finding-text{font-size:1.05rem;font-weight:600;color:#e9d5ff;margin-bottom:6px}
.finding-sub{font-size:0.82rem;color:#94a3b8}
.login-wrap{max-width:440px;margin:0 auto;padding:12px 14px 30px}
.login-hero{text-align:center;padding:8px 0 6px}
.login-hero h1{font-size:1.6rem;font-weight:800;background:linear-gradient(90deg,#e9d5ff,#a5b4fc);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.step-box{background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.08);border-radius:14px;padding:14px;margin:12px 0}
.step-box h3{font-size:0.95rem;margin-bottom:10px;color:#c4b5fd}
.step{display:flex;gap:10px;margin-bottom:10px;align-items:flex-start}
.step-num{min-width:24px;height:24px;border-radius:50%;background:linear-gradient(135deg,#7c3aed,#2563eb);display:flex;align-items:center;justify-content:center;font-size:0.75rem;font-weight:700}
.step-text{font-size:0.84rem;color:#e2e8f0;line-height:1.4}
.video-box{border-radius:14px;overflow:hidden;margin:12px 0;background:#000;aspect-ratio:16/9}
.video-box iframe{width:100%;height:100%;border:0}
.link-btn{display:block;text-align:center;padding:13px;border-radius:12px;margin:10px 0;background:linear-gradient(90deg,#059669,#10b981);color:#fff;font-weight:600;text-decoration:none;font-size:0.95rem}
.form-card{background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.1);border-radius:16px;padding:16px;margin-top:14px}
</style>
"""

ICONS = {
    "home":'<svg viewBox="0 0 24 24"><path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"/></svg>',
    "world":'<svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/></svg>',
    "client":'<svg viewBox="0 0 24 24"><path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z"/></svg>',
    "chat":'<svg viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H6l-2 2V4h16v12z"/></svg>',
    "favourite":'<svg viewBox="0 0 24 24"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/></svg>',
    "account":'<svg viewBox="0 0 24 24"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/></svg>'
}

def nav(active):
    items=[("home","home","/home"),("world","world","/world"),("client","client","/client"),
           ("chat","chat","/chat"),("favourite","favourite","/favourite"),("account","account","/account")]
    h='<div class="bottom-nav">'
    for k,l,u in items:
        c="nav-item active" if active==k else "nav-item"
        h+=f'<a href="{u}" class="{c}">{ICONS[k]}<span>{t(l)}</span></a>'
    return h+'</div>'

def extract_xml(zip_bytes, code):
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            name=next((n for n in zf.namelist() if n.lower().endswith(".xml")),None)
            if not name: return None,"ZIP me XML nahi mili"
            try: return zf.read(name,pwd=code.encode()).decode("utf-8","ignore"),None
            except RuntimeError: return None,"Galat Share Code"
    except Exception as e: return None,str(e)

def parse_xml(xml):
    try:
        clean=re.sub(r'\sxmlns[^"]*"[^"]*"','',xml)
        clean=re.sub(r'\sxmlns:[^=]*="[^"]*"','',clean)
        root=ET.fromstring(clean)
        name=dob=gender=""
        for el in root.iter():
            tag=el.tag.split("}")[-1] if "}" in el.tag else el.tag
            if tag.lower()=="poi":
                name=(el.get("name") or el.get("n") or "").strip()
                dob=(el.get("dob") or el.get("d") or "").strip()
                gender=(el.get("gender") or el.get("g") or "").strip().upper()
                if name: break
        if not name:
            m=re.search(r'name\s*=\s*"([^"]+)"',xml,re.I)
            if m: name=m.group(1).strip()
            m=re.search(r'dob\s*=\s*"([^"]+)"',xml,re.I)
            if m: dob=m.group(1).strip()
            m=re.search(r'gender\s*=\s*"([^"]+)"',xml,re.I)
            if m: gender=m.group(1).strip().upper()
        if not name: return None
        return {"name":name,"dob":dob,"gender":gender}
    except: return None

def age_from(dob):
    dob=(dob or "").strip()
    if not dob: return None
    try:
        if len(dob)==4 and dob.isdigit(): return datetime.date.today().year-int(dob)
        for fmt in ("%d-%m-%Y","%Y-%m-%d","%d/%m/%Y"):
            try:
                d=datetime.datetime.strptime(dob,fmt).date()
                t=datetime.date.today()
                return t.year-d.year-((t.month,t.day)<(d.month,d.day))
            except: continue
        return None
    except: return None

def find_match(my_sid, my_gender, want):
    global WAITING
    now=time.time()
    WAITING=[w for w in WAITING if now-w["ts"]<90 and w["sid"]!=my_sid]
    for i,w in enumerate(WAITING):
        ok1=(want in ("BOTH","") or want==w["gender"] or not w["gender"])
        ok2=(w["want"] in ("BOTH","") or w["want"]==my_gender or not my_gender)
        if ok1 and ok2:
            partner=WAITING.pop(i)
            return partner, str(uuid.uuid4())[:8].upper()
    return None, None

def gen_code():
    return "".join(random.choices(string.ascii_uppercase+string.digits, k=6))

def level_from_score(score):
    # 0-50 L1 ... roughly every 50 points
    return max(1, min(10, 1 + (score or 0) // 50))

# ==================== PAGES ====================
REGISTER = """
<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Limi</title>"""+CSS+"""</head><body>
<div class="splash" id="splash">
  <div class="splash-logo">Limi</div>
  <div class="splash-sub">Verified • Safe • Real</div>
  <div class="splash-bar"><div class="splash-bar-in"></div></div>
</div>
<div class="login-wrap">
  <div class="login-hero"><h1>Limi</h1>
  <p style="color:#94a3b8;font-size:0.88rem;margin-top:4px">Aadhaar Verified • Sirf 18+ • Safe</p></div>
  {% if error %}<div class="error">{{error}}</div>{% endif %}
  {% if success %}<div class="success">Register Successfully 🎉</div>
  <script>setTimeout(()=>location="/home",1300)</script>
  {% else %}
  <div class="step-box">
    <h3>📥 Offline Aadhaar ZIP kaise mile?</h3>
    <div class="step"><div class="step-num">1</div><div class="step-text">Green button pe click → official UIDAI page</div></div>
    <div class="step"><div class="step-num">2</div><div class="step-text">Aadhaar/VID + OTP se login</div></div>
    <div class="step"><div class="step-num">3</div><div class="step-text"><b>4-digit Share Code</b> set karo (yaad rakhna)</div></div>
    <div class="step"><div class="step-num">4</div><div class="step-text">Download → ZIP save</div></div>
    <div class="step"><div class="step-num">5</div><div class="step-text">Yahan ZIP + Share Code se Register</div></div>
  </div>
  <a class="link-btn" href="https://myaadhaar.uidai.gov.in/offline-ekyc" target="_blank" rel="noopener">🔗 ZIP Download Page (Official)</a>
  <div class="step-box">
    <h3>🎬 Video (2 min)</h3>
    <div class="video-box"><iframe src="https://www.youtube.com/embed/G0PCI34YFAg" allowfullscreen></iframe></div>
  </div>
  <div class="form-card">
    <h3 style="text-align:center;margin-bottom:12px">✅ Register</h3>
    <form method="POST" enctype="multipart/form-data">
      <label>Aadhaar Offline ZIP</label>
      <input type="file" name="aadhaar_zip" accept=".zip" required>
      <label>Share Code</label>
      <input type="password" name="share_code" maxlength="20" required placeholder="4 digit">
      <button class="btn btn-primary" style="margin-top:14px">Verify & Register</button>
    </form>
  </div>
  <p style="text-align:center;font-size:0.75rem;color:#64748b;margin-top:14px">Aadhaar number save nahi hota — sirf name + age verify.</p>
  {% endif %}
</div>
<script>setTimeout(()=>{const s=document.getElementById('splash');if(s)s.style.display='none'},2400)</script>
</body></html>
"""

HOME = """
<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Home • Limi</title>"""+CSS+"""</head><body>
<div class="topbar"><div class="logo">Limi</div>
<div class="profile-box">
<div class="avatar">{%if pic%}<img src="{{pic}}">{%else%}{{name[0]|upper}}{%endif%}</div>
<div><div class="pname">{{name}}</div><div class="pstatus">{{verified}}</div>
<a href="/logout" class="logout-btn">{{logout}}</a></div>
</div></div>
<div class="page">
  <div class="home-hero">
    <div class="home-hello">Hey, {{name.split()[0]}} 👋</div>
    <div class="home-sub">Safe verified community</div>
    <span class="home-badge">✓ {{verified}}</span>
    {% if premium %}<span class="home-badge gold">⭐ Premium</span>{% endif %}
    <span class="home-badge">Lv {{level}}</span>
  </div>
  <div class="home-grid">
    <a class="home-tile" href="/world"><div class="emoji">🌍</div><div class="t">World</div><div class="s">Random video</div></a>
    <a class="home-tile" href="/world"><div class="emoji">👥</div><div class="t">Group</div><div class="s">Up to 10</div></a>
    <a class="home-tile" href="/chat"><div class="emoji">💬</div><div class="t">Chat</div><div class="s">Soon</div></a>
    <a class="home-tile" href="/account"><div class="emoji">✨</div><div class="t">Profile</div><div class="s">Level {{level}}</div></a>
  </div>
  <div class="card" style="margin:12px">
    <div style="font-size:0.85rem;color:#94a3b8">This month score</div>
    <div style="font-size:1.3rem;font-weight:700;margin:4px 0">{{score}} pts · Level {{level}}</div>
    <div class="level-bar"><div class="level-fill" style="width:{{level_pct}}%"></div></div>
  </div>
  <div class="home-tip">💡 Boys: Random free. Only Girls/Guys filter = Premium ₹99/mo. Girls: sab free. Level badho → zyada visibility.</div>
</div>
{{nav|safe}}</body></html>
"""

SIMPLE = """
<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{title}}</title>"""+CSS+"""</head><body>
<div class="topbar"><div class="logo">Limi</div></div>
<div class="page"><div class="center" style="padding:40px 16px">
<div style="font-size:2.5rem;margin-bottom:12px">{{emoji}}</div>
<div style="font-size:1.1rem;font-weight:600">{{title}}</div>
<div style="color:#94a3b8;margin-top:6px">{{msg}}</div>
</div></div>{{nav|safe}}</body></html>
"""

WORLD = """
<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>World • Limi</title>"""+CSS+"""</head><body>
<div class="topbar" id="mainTop"><div class="logo">Limi</div></div>
<div class="page" id="startScreen" style="position:relative">
  <div class="start-screen">
    <div class="tap-text">{{tap}}</div>
    <div class="online-count"><span class="online-dot"></span><span id="onlineNum">{{online_count}}</span> {{online}}</div>
    <div class="connect-wrap" onclick="startMatch()">
      <div class="connect-ring"></div><div class="connect-ring"></div><div class="connect-ring"></div>
      <div class="connect-core"></div>
    </div>
  </div>
  <div class="bottom-filters">
    <div class="group-chip" onclick="openGroup()">👥 {{group}} · {{max10}}</div>
    <div class="filter-row">
      <div class="filter-chip" onclick="openGender()">
        <div class="title">🎯 <span id="genderLabel">{{all_g}}</span></div>
        <div class="sub">Girl / Guy / Random</div>
        {% if not is_girl and not premium %}<span class="lock">🔒</span>{% endif %}
      </div>
      <div class="filter-chip" onclick="openPrefs()">
        <div class="title">⚙️ {{prefs}}</div>
        <div class="sub">Age • Language</div>
      </div>
    </div>
  </div>
</div>

<div class="popup-bg" id="genderPopup">
  <div class="popup">
    <h3>🎯 Gender</h3>
    <div class="popup-opt" onclick="trySetGender('F')">👩 {{girl}} {% if not is_girl and not premium %}🔒{% endif %}</div>
    <div class="popup-opt" onclick="trySetGender('M')">👨 {{guy}} {% if not is_girl and not premium %}🔒{% endif %}</div>
    <div class="popup-opt" onclick="trySetGender('BOTH')">🎲 {{random}} ✓ Free</div>
    <div class="popup-opt" style="color:#94a3b8" onclick="closePopups()">Cancel</div>
  </div>
</div>

<div class="popup-bg" id="premiumPopup">
  <div class="popup premium-sheet">
    <h3>⭐ Limi Premium</h3>
    <div class="price">₹99<span style="font-size:0.9rem;font-weight:500">/month</span></div>
    <div class="perks">
      ✓ Only Girls / Only Guys filter<br>
      ✓ Priority matching<br>
      ✓ Support creator reward pool<br>
      ✓ Cancel anytime (demo)
    </div>
    <p style="font-size:0.78rem;color:#94a3b8;margin-bottom:12px">Girls free rehti hain. Boys Random free; filter ke liye Premium.</p>
    <button class="btn btn-gold" onclick="buyPremium()">Activate Premium (Demo)</button>
    <div class="popup-opt" style="color:#94a3b8;margin-top:10px" onclick="closePopups()">Not now</div>
  </div>
</div>

<div class="popup-bg" id="prefsPopup">
  <div class="popup">
    <h3>⚙️ {{prefs}}</h3>
    <label>{{age}}</label>
    <select id="ageMin"><option value="18">18+</option><option value="20">20+</option>
    <option value="22">22+</option><option value="25">25+</option></select>
    <label style="margin-top:10px">{{lang_f}}</label>
    <select id="langFilter"><option value="any">Any</option><option value="hi">Hindi</option>
    <option value="en">English</option><option value="bn">Bengali</option><option value="ta">Tamil</option></select>
    <button class="btn btn-primary" style="margin-top:14px" onclick="applyPrefs()">{{apply}}</button>
  </div>
</div>

<div class="popup-bg" id="groupPopup">
  <div class="popup">
    <h3>👥 {{group}}</h3>
    <div class="info">{{max10}}. Admin code share kare.</div>
    <button class="btn btn-primary" onclick="createGroup()">{{create_g}}</button>
    <div style="text-align:center;margin:12px 0;color:#888">— or —</div>
    <label>Group Code</label>
    <input type="text" id="joinCode" placeholder="ABC123" maxlength="6" style="text-transform:uppercase">
    <button class="btn btn-primary" style="margin-top:10px" onclick="joinGroup()">{{join_g}}</button>
    <div id="groupResult" style="display:none;margin-top:14px">
      <div class="code-box" id="gCode"></div>
      <div style="display:flex;gap:8px;justify-content:center;flex-wrap:wrap">
        <a id="waShare" class="btn" style="background:#25D366;width:auto;padding:10px 14px;text-decoration:none" target="_blank">WhatsApp</a>
        <button class="btn" style="background:#3b82f6;width:auto;padding:10px 14px" onclick="copyLink()">Copy Link</button>
      </div>
    </div>
    <div class="popup-opt" style="color:#94a3b8;margin-top:10px" onclick="closePopups()">Close</div>
  </div>
</div>

<div class="call-screen" id="callScreen">
  <div class="finding-overlay" id="findingUI">
    <div class="finding-rings"><div class="r"></div><div class="r"></div><div class="r"></div><div class="core">✨</div></div>
    <div class="finding-text" id="statusText">{{finding}}</div>
    <div class="finding-sub">Verified 18+ only</div>
  </div>
  <video id="remoteVideo" autoplay playsinline style="display:none"></video>
  <video id="localVideo" autoplay playsinline muted></video>
  <div class="call-top">
    <div class="call-status" id="topStatus"></div>
    <div style="position:relative">
      <button class="menu-btn" onclick="toggleMenu()">⋯</button>
      <div class="menu-dropdown" id="menuDrop">
        <button onclick="doReport()">🚩 {{report}}</button>
        <button onclick="doBlock()">🚫 {{block}}</button>
      </div>
    </div>
  </div>
  <div class="call-bottom">
    <button class="ctrl-btn ctrl-flip" onclick="flipCamera()" title="Flip">🔄</button>
    <button class="ctrl-btn ctrl-next" onclick="nextMatch()">{{next}}</button>
    <button class="ctrl-btn ctrl-end" onclick="stopMatch()">{{end}}</button>
  </div>
</div>
{{nav|safe}}
<script>
let localStream=null,pc=null,roomId=null,isInitiator=false,pollTimer=null,mySid=null,matching=false;
let wantGender="BOTH", facingMode="user", ageMin=18;
const isGirl={{ 'true' if is_girl else 'false' }};
const isPremium={{ 'true' if premium else 'false' }};
const ice={iceServers:[{urls:"stun:stun.l.google.com:19302"},{urls:"stun:stun1.l.google.com:19302"}]};
function $(id){return document.getElementById(id)}
function openGender(){$("genderPopup").style.display="flex"}
function openPrefs(){$("prefsPopup").style.display="flex"}
function openGroup(){$("groupPopup").style.display="flex";$("groupResult").style.display="none"}
function openPremium(){$("premiumPopup").style.display="flex"}
function closePopups(){["genderPopup","prefsPopup","groupPopup","premiumPopup"].forEach(id=>$ (id).style.display="none")}
function trySetGender(g){
  if((g==="F"||g==="M") && !isGirl && !isPremium){closePopups();openPremium();return}
  wantGender=g;
  const L={"F":"{{girl}}","M":"{{guy}}","BOTH":"{{random}}"};
  $("genderLabel").innerText=L[g]||"{{all_g}}";
  closePopups();
}
function applyPrefs(){ageMin=parseInt($("ageMin").value)||18;closePopups()}
function toggleMenu(){const m=$("menuDrop");m.style.display=m.style.display==="block"?"none":"block"}
async function buyPremium(){
  const r=await fetch("/premium/buy",{method:"POST"});
  const d=await r.json();
  if(d.ok){alert("Premium activated 30 days (demo)!");location.reload()}
  else alert(d.error||"Failed");
}
async function createGroup(){
  const r=await fetch("/group/create",{method:"POST"}); const d=await r.json();
  if(d.code){$("gCode").innerText=d.code;$("groupResult").style.display="block";
    const link=location.origin+"/group/"+d.code;
    $("waShare").href="https://wa.me/?text="+encodeURIComponent("Join Limi group: "+link+" Code: "+d.code);
    window._groupLink=link}
}
function copyLink(){if(window._groupLink){navigator.clipboard.writeText(window._groupLink);alert("Copied!")}}
async function joinGroup(){
  const code=($("joinCode").value||"").trim().toUpperCase();
  if(!code){alert("Code daalo");return}
  const r=await fetch("/group/join",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({code})});
  const d=await r.json();
  if(d.ok){alert("Joined!");closePopups()} else alert(d.error||"Invalid");
}
async function startMatch(){
  if(matching) return;
  if((wantGender==="F"||wantGender==="M") && !isGirl && !isPremium){openPremium();return}
  matching=true;
  $("startScreen").style.display="none";$("mainTop").style.display="none";
  document.querySelector(".bottom-nav").style.display="none";
  $("callScreen").style.display="flex";$("findingUI").style.display="flex";
  $("remoteVideo").style.display="none";$("statusText").innerText="{{finding}}";
  await startCam();
  const res=await fetch("/match",{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({want:wantGender})});
  const data=await res.json();
  if(data.error==="premium"){matching=false;stopMatch();openPremium();return}
  mySid=data.sid;
  if(data.matched){roomId=data.room;isInitiator=data.initiator;onConnected();await setupPeer(true);startPoll()}
  else pollForMatch();
}
async function pollForMatch(){
  if(!matching) return;
  try{
    const res=await fetch("/match/status?sid="+mySid); const data=await res.json();
    if(data.matched){roomId=data.room;isInitiator=data.initiator;onConnected();await setupPeer(true);startPoll();return}
    if(data.online!==undefined)$("onlineNum").innerText=data.online;
  }catch(e){}
  setTimeout(pollForMatch,1400);
}
function onConnected(){
  $("findingUI").style.display="none";$("remoteVideo").style.display="block";
  $("topStatus").innerText="{{connected}}";
  fetch("/stats/talk",{method:"POST"});
}
async function startCam(){
  try{
    if(localStream) localStream.getTracks().forEach(t=>t.stop());
    localStream=await navigator.mediaDevices.getUserMedia({video:{facingMode},audio:true});
    $("localVideo").srcObject=localStream;
    if(pc){const sender=pc.getSenders().find(s=>s.track&&s.track.kind==="video");
      if(sender) sender.replaceTrack(localStream.getVideoTracks()[0]);}
  }catch(e){alert("Camera: "+e.message)}
}
async function flipCamera(){
  facingMode = facingMode==="user" ? "environment" : "user";
  await startCam();
}
async function setupPeer(initiator){
  pc=new RTCPeerConnection(ice);
  if(localStream) localStream.getTracks().forEach(t=>pc.addTrack(t,localStream));
  pc.ontrack=e=>{$("remoteVideo").srcObject=e.streams[0];onConnected()};
  pc.onicecandidate=e=>{if(e.candidate)sendSig({type:"candidate",candidate:e.candidate})};
  if(initiator){const offer=await pc.createOffer();await pc.setLocalDescription(offer);sendSig({type:"offer",sdp:offer})}
}
function sendSig(data){fetch("/signal",{method:"POST",headers:{"Content-Type":"application/json"},
  body:JSON.stringify({room:roomId,data:data,from:isInitiator?"a":"b"})})}
function startPoll(){pollTimer=setInterval(async()=>{try{
  const r=await fetch("/signal?room="+roomId+"&me="+(isInitiator?"a":"b"));
  for(const m of await r.json()) await handleSig(m)}catch(e){}},900)}
async function handleSig(msg){
  if(!pc)return;
  if(msg.type==="offer"&&!isInitiator){await pc.setRemoteDescription(new RTCSessionDescription(msg.sdp));
    const ans=await pc.createAnswer();await pc.setLocalDescription(ans);sendSig({type:"answer",sdp:ans})}
  else if(msg.type==="answer"&&isInitiator){await pc.setRemoteDescription(new RTCSessionDescription(msg.sdp))}
  else if(msg.type==="candidate"){try{await pc.addIceCandidate(new RTCIceCandidate(msg.candidate))}catch(e){}}
}
function cleanup(){if(pollTimer){clearInterval(pollTimer);pollTimer=null}if(pc){pc.close();pc=null}
  if(localStream){localStream.getTracks().forEach(t=>t.stop());localStream=null}
  $("localVideo").srcObject=null;$("remoteVideo").srcObject=null;roomId=null}
function stopMatch(){matching=false;cleanup();
  fetch("/match/leave",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({sid:mySid})});
  $("callScreen").style.display="none";$("startScreen").style.display="block";
  $("mainTop").style.display="flex";document.querySelector(".bottom-nav").style.display="flex";refreshOnline()}
function nextMatch(){cleanup();matching=false;
  fetch("/match/leave",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({sid:mySid})});
  setTimeout(startMatch,350)}
function doReport(){fetch("/report",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({room:roomId})});
  $("menuDrop").style.display="none";nextMatch()}
function doBlock(){fetch("/report",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({room:roomId,block:true})});
  $("menuDrop").style.display="none";nextMatch()}
async function refreshOnline(){try{const r=await fetch("/online");const d=await r.json();$("onlineNum").innerText=d.count||0}catch(e){}}
setInterval(refreshOnline,5000);refreshOnline();
</script>
</body></html>
"""

ACCOUNT = """
<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Account</title>"""+CSS+"""</head><body>
<div class="topbar"><div class="logo">Limi</div></div>
<div class="page" style="padding:14px">
<div class="card" style="text-align:center">
<div class="avatar" style="width:72px;height:72px;margin:0 auto 10px;font-size:1.7rem">
{%if pic%}<img src="{{pic}}">{%else%}{{name[0]|upper}}{%endif%}</div>
<div style="font-size:1.1rem;font-weight:600">{{name}}</div>
<div style="font-size:0.76rem;color:#4ade80;margin:4px 0">{{verified}} · Lv {{level}}</div>
{% if premium %}<div style="color:#fbbf24;font-size:0.85rem;margin-top:4px">⭐ Premium active</div>{% endif %}
<div style="margin-top:10px">Score: <b>{{score}}</b> · {{likes}}: <b>{{like_count}}</b></div>
<div class="level-bar" style="margin-top:10px"><div class="level-fill" style="width:{{level_pct}}%"></div></div>
</div>
{% if is_girl %}
<div class="card">
<div style="font-weight:600;margin-bottom:6px">Creator pool (demo)</div>
<div style="font-size:0.85rem;color:#94a3b8">Monthly payout 1st pe performance se. Direct subscription nahi — level + talk score se.</div>
<div style="margin-top:8px;font-size:1.1rem">Est. share: ₹{{est_earn}}</div>
</div>
{% else %}
<div class="card">
{% if not premium %}
<button class="btn btn-gold" onclick="location.href='/world'">⭐ Go Premium ₹99/mo</button>
<p style="font-size:0.78rem;color:#94a3b8;margin-top:8px;text-align:center">Only Girls/Guys filter unlock</p>
{% else %}
<div style="color:#fbbf24;text-align:center">Premium until {{premium_until}}</div>
{% endif %}
</div>
{% endif %}
<div class="card">
<form method="POST" enctype="multipart/form-data">
<label>{{upload_photo}}</label>
<input type="file" name="photo" accept="image/*">
<button class="btn btn-primary" name="action" value="photo" style="margin-top:10px">{{save}}</button>
</form></div>
<div class="card">
<form method="POST">
<label>{{select_lang}}</label>
<select name="lang">
<option value="en" {%if lang=='en'%}selected{%endif%}>English</option>
<option value="hi" {%if lang=='hi'%}selected{%endif%}>हिन्दी</option>
</select>
<button class="btn btn-primary" name="action" value="lang" style="margin-top:10px">{{save}}</button>
</form></div>
</div>{{nav|safe}}</body></html>
"""

# ==================== ROUTES ====================
@app.route("/")
def index():
    return redirect("/home" if session.get("name") else "/register")

@app.route("/register", methods=["GET","POST"])
def register():
    if session.get("name"): return redirect("/home")
    error=success=None
    if request.method=="POST":
        zf=request.files.get("aadhaar_zip")
        code=(request.form.get("share_code") or "").strip()
        if not zf or not code: error="ZIP + Share Code zaroori"
        else:
            xml,err=extract_xml(zf.read(),code)
            if err: error=err
            else:
                data=parse_xml(xml)
                if not data: error="XML se name nahi mila"
                else:
                    age=age_from(data["dob"])
                    if age is not None and age<18: error=f"Age {age}. 18+ only"
                    else:
                        session["name"]=data["name"]
                        g=(data.get("gender") or "").upper()
                        session["gender"]="M" if g.startswith("M") else ("F" if g.startswith("F") else "")
                        session["likes"]=0; session["lang"]="en"; session["pic"]=None
                        session["sid"]=str(uuid.uuid4())[:10]
                        session["score"]=0; session["talks"]=0
                        session.pop("premium_until", None)
                        success=True
    return render_template_string(REGISTER, error=error, success=success)

@app.route("/home")
def home():
    if not session.get("name"): return redirect("/register")
    score=session.get("score",0)
    level=level_from_score(score)
    return render_template_string(HOME, name=session["name"], pic=session.get("pic"),
        verified=t("verified"), logout=t("logout"), nav=nav("home"),
        premium=is_premium(), level=level, score=score, level_pct=min(100,(score%50)*2))

@app.route("/world")
def world():
    if not session.get("name"): return redirect("/register")
    if session["name"] in BANNED:
        return "<h3 style='color:#fff;text-align:center;margin-top:40px'>Banned</h3>"
    online=len([w for w in WAITING if time.time()-w["ts"]<90])
    return render_template_string(WORLD,
        tap=t("tap"), online=t("online"), online_count=online,
        girl=t("girl"), guy=t("guy"), random=t("random"), prefs=t("prefs"),
        age=t("age"), lang_f=t("lang_f"), apply=t("apply"), all_g=t("all_g"),
        finding=t("finding"), connected=t("connected"),
        next=t("next"), report=t("report"), block=t("block"), end=t("end"),
        group=t("group"), max10=t("max10"), create_g=t("create_g"), join_g=t("join_g"),
        is_girl=is_girl(), premium=is_premium(), nav=nav("world"))

@app.route("/client")
def client():
    if not session.get("name"): return redirect("/register")
    return render_template_string(SIMPLE, title=t("client"), msg=t("coming"), emoji="👤", nav=nav("client"))

@app.route("/chat")
def chat():
    if not session.get("name"): return redirect("/register")
    return render_template_string(SIMPLE, title=t("chat"), msg=t("chat_soon"), emoji="💬", nav=nav("chat"))

@app.route("/favourite")
def favourite():
    if not session.get("name"): return redirect("/register")
    return render_template_string(SIMPLE, title=t("favourite"), msg=t("coming"), emoji="❤️", nav=nav("favourite"))

@app.route("/account", methods=["GET","POST"])
def account():
    if not session.get("name"): return redirect("/register")
    if request.method=="POST":
        act=request.form.get("action")
        if act=="lang":
            lg=request.form.get("lang","en")
            if lg in ("en","hi"): session["lang"]=lg
        elif act=="photo":
            ph=request.files.get("photo")
            if ph and ph.filename:
                try:
                    d=ph.read()
                    if len(d)<1500000:
                        b64=base64.b64encode(d).decode()
                        ext="png" if ph.filename.lower().endswith(".png") else "jpeg"
                        session["pic"]=f"data:image/{ext};base64,{b64}"
                except: pass
    score=session.get("score",0)
    level=level_from_score(score)
    # demo earn: girls get visual estimate from score
    est = (score // 10) * 15 if is_girl() else 0
    pu = session.get("premium_until","")[:10] if session.get("premium_until") else ""
    return render_template_string(ACCOUNT, name=session["name"], pic=session.get("pic"),
        like_count=session.get("likes",0), lang=session.get("lang","en"),
        verified=t("verified"), likes=t("likes"), upload_photo=t("upload_photo"),
        select_lang=t("select_lang"), save=t("save"), nav=nav("account"),
        level=level, score=score, level_pct=min(100,(score%50)*2),
        premium=is_premium(), is_girl=is_girl(), est_earn=est, premium_until=pu)

@app.route("/logout")
def logout():
    sid=session.get("sid")
    global WAITING
    WAITING=[w for w in WAITING if w["sid"]!=sid]
    session.clear()
    return redirect("/register")

@app.route("/premium/buy", methods=["POST"])
def premium_buy():
    if not session.get("name"): return jsonify({"ok":False}),401
    if is_girl(): return jsonify({"ok":False,"error":"Girls already free"})
    # Mock: 30 days premium + add to pool
    until = datetime.datetime.utcnow() + datetime.timedelta(days=30)
    session["premium_until"] = until.isoformat()
    global CREDIT_POOL
    CREDIT_POOL += 99
    return jsonify({"ok":True,"until":until.isoformat(),"pool":CREDIT_POOL})

@app.route("/stats/talk", methods=["POST"])
def stats_talk():
    if not session.get("name"): return jsonify({"ok":False})
    session["score"] = session.get("score",0) + 5
    session["talks"] = session.get("talks",0) + 1
    return jsonify({"ok":True,"score":session["score"]})

@app.route("/online")
def online():
    now=time.time()
    return jsonify({"count": len([w for w in WAITING if now-w["ts"]<90])})

@app.route("/match", methods=["POST"])
def match():
    if not session.get("name"): return jsonify({"error":"auth"}),401
    body=request.get_json(force=True,silent=True) or {}
    want=(body.get("want") or "BOTH").upper()
    if want not in ("BOTH","M","F"): want="BOTH"
    if not can_use_filter(want):
        return jsonify({"error":"premium","msg":"Premium required for this filter"})
    my_gender=session.get("gender") or ""
    sid=session.get("sid") or str(uuid.uuid4())[:10]
    session["sid"]=sid
    partner, room = find_match(sid, my_gender, want)
    if partner:
        return jsonify({"matched":True,"room":room,"initiator":True,"sid":sid})
    WAITING.append({"sid":sid,"name":session["name"],"gender":my_gender,"want":want,"ts":time.time()})
    return jsonify({"matched":False,"sid":sid})

@app.route("/match/status")
def match_status():
    sid=request.args.get("sid")
    online=len([w for w in WAITING if time.time()-w["ts"]<90])
    if not sid: return jsonify({"matched":False,"online":online})
    me=next((w for w in WAITING if w["sid"]==sid),None)
    if not me: return jsonify({"matched":False,"online":online})
    partner, room = find_match(sid, me["gender"], me["want"])
    if partner:
        return jsonify({"matched":True,"room":room,"initiator":True,"online":online})
    return jsonify({"matched":False,"online":online})

@app.route("/match/leave", methods=["POST"])
def match_leave():
    body=request.get_json(force=True,silent=True) or {}
    sid=body.get("sid")
    global WAITING
    WAITING=[w for w in WAITING if w["sid"]!=sid]
    return jsonify({"ok":True})

@app.route("/group/create", methods=["POST"])
def group_create():
    if not session.get("name"): return jsonify({"error":"auth"}),401
    code=gen_code()
    GROUPS[code]={"admin":session["name"],"members":[session["name"]],"created":time.time()}
    return jsonify({"code":code})

@app.route("/group/join", methods=["POST"])
def group_join():
    if not session.get("name"): return jsonify({"error":"auth"}),401
    body=request.get_json(force=True,silent=True) or {}
    code=(body.get("code") or "").upper()
    if code not in GROUPS: return jsonify({"ok":False,"error":"Invalid code"})
    g=GROUPS[code]
    if len(g["members"])>=10: return jsonify({"ok":False,"error":"Group full"})
    if session["name"] not in g["members"]: g["members"].append(session["name"])
    return jsonify({"ok":True,"members":len(g["members"])})

@app.route("/group/<code>")
def group_link(code):
    if not session.get("name"): return redirect("/register")
    return redirect("/world")

@app.route("/report", methods=["POST"])
def report():
    body=request.get_json(force=True,silent=True) or {}
    key=body.get("room") or "x"
    REPORTS[key]=REPORTS.get(key,0)+1
    if body.get("block") or REPORTS[key]>=3: BANNED.add(key)
    return jsonify({"ok":True})

@app.route("/signal", methods=["GET","POST"])
def signal():
    if request.method=="POST":
        body=request.get_json(force=True,silent=True) or {}
        room=(body.get("room") or "").upper()
        data=body.get("data"); frm=body.get("from","a")
        if not room or not data: return jsonify({"ok":False})
        if room not in ROOMS: ROOMS[room]=[]
        ROOMS[room].append({"to":"b" if frm=="a" else "a","data":data})
        ROOMS[room]=ROOMS[room][-25:]
        return jsonify({"ok":True})
    room=(request.args.get("room") or "").upper()
    me=request.args.get("me","a")
    if room not in ROOMS: return jsonify([])
    mine=[m["data"] for m in ROOMS[room] if m["to"]==me]
    ROOMS[room]=[m for m in ROOMS[room] if m["to"]!=me]
    return jsonify(mine)

if __name__=="__main__":
    print("="*50)
    print("  Limi Premium v2")
    print("  http://127.0.0.1:5000")
    print("="*50)
    app.run(debug=False, host="0.0.0.0", port=5000)
