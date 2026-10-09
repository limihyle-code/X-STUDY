#!/usr/bin/env python3
"""
Limi — Signup/Signin + Aadhaar verify + SQLite match (Render-ready)
"""
import os, io, zipfile, datetime, base64, re, time, uuid, random, string, hashlib, secrets, sqlite3
from xml.etree import ElementTree as ET
from flask import Flask, request, render_template_string, redirect, session, jsonify

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "limi-prod-change-me-2026")
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

ROOMS, GROUPS, REPORTS, BANNED = {}, {}, {}, set()
CREDIT_POOL = 0
# ---------- DB (SQLite local / Postgres on Render) ----------
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
USE_PG = DATABASE_URL.startswith("postgres")
if USE_PG and DATABASE_URL.startswith("postgres://"):
    # SQLAlchemy/psycopg sometimes need postgresql://
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

DB_PATH = os.environ.get("LIMI_DB", os.path.join(os.path.dirname(__file__) or ".", "limi.db"))

def db():
    if USE_PG:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False
        return conn
    c = sqlite3.connect(DB_PATH, timeout=15)
    c.row_factory = sqlite3.Row
    try:
        c.execute("PRAGMA journal_mode=WAL")
    except Exception:
        pass
    return c

def _cursor(conn):
    if USE_PG:
        import psycopg2.extras
        return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return conn.cursor()

def db_init():
    conn = db()
    try:
        cur = _cursor(conn)
        if USE_PG:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS users(
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                email TEXT,
                phone TEXT,
                pass_hash TEXT NOT NULL,
                name TEXT NOT NULL,
                gender TEXT,
                ref_id TEXT UNIQUE,
                score INTEGER DEFAULT 0,
                talks INTEGER DEFAULT 0,
                likes INTEGER DEFAULT 0,
                premium_until TEXT,
                pic TEXT,
                lang TEXT DEFAULT 'en',
                created DOUBLE PRECISION
            );
            CREATE TABLE IF NOT EXISTS waiting(
                sid TEXT PRIMARY KEY, name TEXT, gender TEXT, want TEXT, ts DOUBLE PRECISION, user_id INTEGER
            );
            CREATE TABLE IF NOT EXISTS presence(
                sid TEXT PRIMARY KEY, name TEXT, gender TEXT, ts DOUBLE PRECISION, user_id INTEGER
            );
            """)
        else:
            cur.executescript("""
            CREATE TABLE IF NOT EXISTS users(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT, phone TEXT, pass_hash TEXT NOT NULL,
                name TEXT NOT NULL, gender TEXT, ref_id TEXT UNIQUE,
                score INTEGER DEFAULT 0, talks INTEGER DEFAULT 0, likes INTEGER DEFAULT 0,
                premium_until TEXT, pic TEXT, lang TEXT DEFAULT 'en', created REAL
            );
            CREATE TABLE IF NOT EXISTS waiting(
                sid TEXT PRIMARY KEY, name TEXT, gender TEXT, want TEXT, ts REAL, user_id INTEGER
            );
            CREATE TABLE IF NOT EXISTS presence(
                sid TEXT PRIMARY KEY, name TEXT, gender TEXT, ts REAL, user_id INTEGER
            );
            """)
        conn.commit()
    finally:
        conn.close()

db_init()

def q(sql, args=None, fetchone=False, fetchall=False, commit=False):
    """Run query. For Postgres convert ? to %s"""
    args = args or ()
    if USE_PG:
        sql = sql.replace("?", "%s")
    conn = db()
    try:
        cur = _cursor(conn)
        cur.execute(sql, args)
        result = None
        if fetchone:
            row = cur.fetchone()
            result = dict(row) if row and USE_PG else row
        elif fetchall:
            rows = cur.fetchall()
            result = [dict(r) if USE_PG else r for r in rows]
        if commit:
            conn.commit()
        elif not fetchone and not fetchall:
            conn.commit()
        return result
    finally:
        conn.close()


def hash_pw(password, salt=None):
    salt = salt or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120000)
    return f"{salt}${h.hex()}"

def check_pw(password, stored):
    try:
        salt, hx = stored.split("$", 1)
        h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120000)
        return h.hex() == hx
    except Exception:
        return False

def _row(r):
    if r is None: return None
    if USE_PG: return dict(r)
    return r

def user_by_login(login):
    login = (login or "").strip()
    return q("SELECT * FROM users WHERE username=? OR email=? OR phone=? LIMIT 1",
             (login, login, login), fetchone=True)

def user_by_id(uid):
    return q("SELECT * FROM users WHERE id=?", (uid,), fetchone=True)

def presence_ping(sid, name, gender, user_id=None):
    now = time.time()
    if USE_PG:
        q("INSERT INTO presence(sid,name,gender,ts,user_id) VALUES(?,?,?,?,?) ON CONFLICT(sid) DO UPDATE SET name=EXCLUDED.name, gender=EXCLUDED.gender, ts=EXCLUDED.ts, user_id=EXCLUDED.user_id",
          (sid, name, gender or "", now, user_id), commit=True)
    else:
        q("INSERT OR REPLACE INTO presence(sid,name,gender,ts,user_id) VALUES(?,?,?,?,?)",
          (sid, name, gender or "", now, user_id), commit=True)
    q("DELETE FROM presence WHERE ts < ?", (now - 60,), commit=True)
    row = q("SELECT COUNT(*) AS c FROM presence WHERE ts >= ?", (now - 45,), fetchone=True)
    return int(row["c"] if USE_PG or isinstance(row, dict) else row[0])

def online_count():
    now = time.time()
    q("DELETE FROM presence WHERE ts < ?", (now - 60,), commit=True)
    q("DELETE FROM waiting WHERE ts < ?", (now - 90,), commit=True)
    p = q("SELECT COUNT(*) AS c FROM presence WHERE ts >= ?", (now - 45,), fetchone=True)
    w = q("SELECT COUNT(*) AS c FROM waiting WHERE ts >= ?", (now - 90,), fetchone=True)
    def n(r):
        return int(r["c"] if isinstance(r, dict) else r[0])
    return max(n(p), n(w)), n(w)

def waiting_add(sid, name, gender, want, user_id=None):
    now = time.time()
    q("DELETE FROM waiting WHERE sid=?", (sid,), commit=True)
    q("INSERT INTO waiting(sid,name,gender,want,ts,user_id) VALUES(?,?,?,?,?,?)",
      (sid, name, gender or "", want or "BOTH", now, user_id), commit=True)

def waiting_leave(sid):
    q("DELETE FROM waiting WHERE sid=?", (sid,), commit=True)

def find_match_db(my_sid, my_gender, want):
    now = time.time()
    q("DELETE FROM waiting WHERE ts < ?", (now - 90,), commit=True)
    rows = q("SELECT * FROM waiting WHERE sid != ? ORDER BY ts ASC", (my_sid,), fetchall=True) or []
    for w in rows:
        w = dict(w) if not isinstance(w, dict) else w
        their_want = (w.get("want") or "BOTH").upper()
        their_gender = (w.get("gender") or "").upper()
        my_want = (want or "BOTH").upper()
        mg = (my_gender or "").upper()
        ok1 = my_want in ("BOTH", "") or my_want == their_gender or not their_gender
        ok2 = their_want in ("BOTH", "") or their_want == mg or not mg
        if ok1 and ok2:
            q("DELETE FROM waiting WHERE sid=? OR sid=?", (my_sid, w["sid"]), commit=True)
            return w, str(uuid.uuid4())[:8].upper()
    return None, None

# ---------- Aadhaar ----------
def extract_xml(zip_bytes, code):
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            name = next((n for n in zf.namelist() if n.lower().endswith(".xml")), None)
            if not name:
                return None, "ZIP me XML nahi mili"
            try:
                return zf.read(name, pwd=code.encode()).decode("utf-8", "ignore"), None
            except RuntimeError:
                return None, "Galat Share Code"
    except Exception as e:
        return None, str(e)

def parse_xml(xml):
    try:
        clean = re.sub(r'\sxmlns[^"]*"[^"]*"', '', xml)
        clean = re.sub(r'\sxmlns:[^=]*="[^"]*"', '', clean)
        root = ET.fromstring(clean)
        name = dob = gender = ""
        for el in root.iter():
            tag = el.tag.split("}")[-1] if "}" in el.tag else el.tag
            if tag.lower() == "poi":
                name = (el.get("name") or el.get("n") or "").strip()
                dob = (el.get("dob") or el.get("d") or "").strip()
                gender = (el.get("gender") or el.get("g") or "").strip().upper()
                if name:
                    break
        if not name:
            m = re.search(r'name\s*=\s*"([^"]+)"', xml, re.I)
            if m: name = m.group(1).strip()
            m = re.search(r'dob\s*=\s*"([^"]+)"', xml, re.I)
            if m: dob = m.group(1).strip()
            m = re.search(r'gender\s*=\s*"([^"]+)"', xml, re.I)
            if m: gender = m.group(1).strip().upper()
        if not name:
            return None
        ref = ""
        try:
            ref = root.get("referenceId") or root.get("referenceid") or ""
            if not ref:
                m = re.search(r'referenceId\s*=\s*"([^"]+)"', xml, re.I)
                if m: ref = m.group(1)
        except Exception:
            pass
        return {"name": name, "dob": dob, "gender": gender, "reference_id": ref}
    except Exception:
        return None

def age_from(dob):
    dob = (dob or "").strip()
    if not dob:
        return None
    try:
        if len(dob) == 4 and dob.isdigit():
            return datetime.date.today().year - int(dob)
        for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y"):
            try:
                d = datetime.datetime.strptime(dob, fmt).date()
                t = datetime.date.today()
                return t.year - d.year - ((t.month, t.day) < (d.month, d.day))
            except Exception:
                continue
        return None
    except Exception:
        return None

def verify_uidai_signature(xml_str):
    """
    Returns (ok, code, message)
    codes: ok | no_sig | no_poi | crypto_fail | parse_error
    """
    if os.environ.get("SKIP_SIGNATURE") == "1":
        return True, "ok", "skipped"

    raw = xml_str if isinstance(xml_str, str) else xml_str.decode("utf-8", "ignore")
    has_sig = ("<Signature" in raw) or ("Signature xmlns" in raw) or ("ds:Signature" in raw)
    has_poi = ("Poi " in raw) or ("<Poi" in raw) or ('name="' in raw)
    has_ref = ("referenceId" in raw) or ("referenceid" in raw.lower())

    if not has_sig:
        return False, "no_sig", (
            "You are not eligible for Limi. "
            "ZIP me UIDAI digital signature nahi mili — file edit/fake ho sakti hai. "
            "Sirf official myAadhaar se naya Offline e-KYC ZIP download karke try karo."
        )
    if not has_poi:
        return False, "no_poi", (
            "You are not eligible for Limi. "
            "ZIP me valid Aadhaar name/data nahi mili. Galat ya edited file."
        )

    # Try cryptographic verify when libraries present
    try:
        from signxml import XMLVerifier
        from lxml import etree
        root = etree.fromstring(raw.encode("utf-8"))
        crypto_ok = False
        try:
            XMLVerifier().verify(root, require_x509=False)
            crypto_ok = True
        except Exception:
            try:
                XMLVerifier().verify(root)
                crypto_ok = True
            except Exception:
                crypto_ok = False

        if crypto_ok:
            return True, "ok", "signature-ok"

        # Crypto failed — likely modified OR missing official cert chain
        strict = os.environ.get("STRICT_SIGNATURE", "0") == "1"
        if strict:
            return False, "crypto_fail", (
                "You are not eligible for Limi. "
                "Aadhaar ZIP ki digital signature match nahi hui. "
                "Possible: name/age/gender edit karke upload kiya gaya hai, ya file corrupt hai. "
                "Official myAadhaar se FRESH Offline e-KYC ZIP download karke Share Code ke saath dobara try karo."
            )
        return True, "ok", "structure-ok"
    except ImportError:
        # No signxml — structure only
        return True, "ok", "soft-check"
    except Exception:
        strict = os.environ.get("STRICT_SIGNATURE", "0") == "1"
        if strict:
            return False, "crypto_fail", (
                "You are not eligible for Limi. "
                "ZIP verify nahi ho payi. Fake/edited file ho sakti hai. "
                "Official site se naya ZIP download karke try karo."
            )
        return True, "ok", "structure-ok"


def t(key):
    L = {
        "en": {"home":"Home","world":"World","client":"Client","chat":"Chat","favourite":"Favourite",
               "account":"My Account","logout":"Logout","verified":"Verified 18+","likes":"Likes",
               "save":"Save","upload_photo":"Upload Photo","select_lang":"Language","coming":"Coming Soon",
               "tap":"Tap to start video chatting","online":"online","girl":"Girl","guy":"Guy",
               "random":"Random","prefs":"Preferences","age":"Age","lang_f":"Language","apply":"Apply",
               "finding":"Connecting you to someone special...","connected":"Connected","next":"Next",
               "report":"Report","block":"Block","end":"End","all_g":"All Genders","group":"Add Group",
               "create_g":"Create Group","join_g":"Join with Code","max10":"Up to 10 people",
               "chat_soon":"Real chat coming soon","premium":"Go Premium"},
        "hi": {"home":"होम","world":"वर्ल्ड","client":"क्लाइंट","chat":"चैट","favourite":"पसंदीदा",
               "account":"मेरा अकाउंट","logout":"लॉगआउट","verified":"वेरिफाइड 18+","likes":"लाइक्स",
               "save":"सेव","upload_photo":"फोटो अपलोड","select_lang":"भाषा","coming":"जल्द",
               "tap":"वीडियो चैट शुरू करें","online":"ऑनलाइन","girl":"लड़की","guy":"लड़का",
               "random":"रैंडम","prefs":"फ़िल्टर","age":"उम्र","lang_f":"भाषा","apply":"लागू",
               "finding":"कनेक्ट हो रहा है...","connected":"कनेक्टेड","next":"अगला",
               "report":"रिपोर्ट","block":"ब्लॉक","end":"बंद","all_g":"सभी","group":"ग्रुप",
               "create_g":"ग्रुप बनाएं","join_g":"कोड से जॉइन","max10":"अधिकतम 10",
               "chat_soon":"चैट जल्द","premium":"प्रीमियम"}
    }
    return L.get(session.get("lang", "en"), L["en"]).get(key, key)

def is_premium():
    exp = session.get("premium_until")
    if not exp:
        return False
    try:
        return datetime.datetime.fromisoformat(exp) > datetime.datetime.utcnow()
    except Exception:
        return False

def is_girl():
    return (session.get("gender") or "") == "F"

def can_use_filter(want):
    if is_girl() or is_premium():
        return True
    return want in ("BOTH", "RANDOM", "")

def level_from_score(score):
    return max(1, min(10, 1 + (score or 0) // 50))

def load_session_user(u):
    session["user_id"] = u["id"]
    session["name"] = u["name"]
    session["username"] = u["username"]
    session["gender"] = u["gender"] or ""
    session["score"] = u["score"] or 0
    session["likes"] = u["likes"] or 0
    session["lang"] = u["lang"] or "en"
    session["pic"] = u["pic"]
    session["premium_until"] = u["premium_until"]
    session["sid"] = session.get("sid") or str(uuid.uuid4())[:12]

CSS = """
<style>
*{box-sizing:border-box;margin:0;padding:0;font-family:system-ui,-apple-system,sans-serif}
body{background:linear-gradient(180deg,#1a1050 0%,#0f0a2e 45%,#0a0618 100%);min-height:100vh;color:#eee;padding-bottom:64px}
.topbar{display:flex;justify-content:space-between;align-items:center;padding:12px 16px;background:rgba(0,0,0,.15);border-bottom:1px solid rgba(255,255,255,.05)}
.logo{font-size:1.2rem;font-weight:700;background:linear-gradient(90deg,#c4b5fd,#60a5fa);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.avatar{width:36px;height:36px;border-radius:50%;background:linear-gradient(135deg,#7c3aed,#2563eb);display:flex;align-items:center;justify-content:center;font-weight:700;overflow:hidden}
.avatar img{width:100%;height:100%;object-fit:cover}
.pname{font-weight:600;font-size:.85rem}.pstatus{font-size:.65rem;color:#4ade80}
.logout-btn{color:#f87171;font-size:.72rem;text-decoration:none}
.bottom-nav{position:fixed;bottom:0;left:0;right:0;height:60px;background:rgba(12,8,35,.97);border-top:1px solid rgba(255,255,255,.07);display:flex;justify-content:space-around;align-items:center;z-index:100}
.nav-item{display:flex;flex-direction:column;align-items:center;text-decoration:none;color:#666;font-size:.6rem;width:16%}
.nav-item.active{color:#a78bfa}
.nav-item svg{width:20px;height:20px;margin-bottom:2px;fill:currentColor}
.card{background:rgba(255,255,255,.06);border-radius:16px;padding:16px;margin:12px;border:1px solid rgba(255,255,255,.08)}
label{display:block;margin:8px 0 4px;font-size:.84rem;color:#a5b4fc}
input,select{width:100%;padding:11px;border-radius:10px;border:1px solid #444;background:rgba(0,0,0,.3);color:#fff;font-size:.9rem}
.btn{border:none;border-radius:12px;padding:12px 18px;font-weight:600;font-size:.92rem;cursor:pointer;color:#fff}
.btn-primary{background:linear-gradient(90deg,#7c3aed,#2563eb);width:100%}
.btn-gold{background:linear-gradient(90deg,#b45309,#f59e0b);width:100%}
.btn-ghost{background:rgba(255,255,255,.08);width:100%;margin-top:8px}
.success{background:#065f46;color:#fff;padding:12px;border-radius:10px;text-align:center;margin:10px}
.error{background:#7f1d1d;color:#fff;padding:10px;border-radius:8px;margin:10px;font-size:.9rem}
.info{background:rgba(99,102,241,.12);border-left:3px solid #818cf8;padding:10px;border-radius:0 8px 8px 0;margin:10px;font-size:.84rem;color:#c7d2fe}
.tabs{display:flex;gap:8px;margin-bottom:12px}
.tab{flex:1;text-align:center;padding:12px;border-radius:12px;background:rgba(255,255,255,.05);cursor:pointer;font-weight:600}
.tab.on{background:rgba(167,139,250,.25);color:#c4b5fd}
.wrap{max-width:440px;margin:0 auto;padding:16px}
.home-hero{text-align:center;padding:24px 16px 8px}
.home-hello{font-size:1.35rem;font-weight:700}
.home-badge{display:inline-block;background:rgba(74,222,128,.15);color:#4ade80;padding:4px 12px;border-radius:20px;font-size:.75rem;margin:4px}
.home-badge.gold{background:rgba(245,158,11,.2);color:#fbbf24}
.home-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;padding:12px}
.home-tile{background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.08);border-radius:16px;padding:16px;text-align:center;text-decoration:none;color:#eee}
.level-bar{height:6px;background:rgba(255,255,255,.1);border-radius:4px;overflow:hidden;margin-top:8px}
.level-fill{height:100%;background:linear-gradient(90deg,#a78bfa,#60a5fa)}
.start-screen{display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:calc(100vh - 200px);padding:16px;text-align:center}
.connect-wrap{position:relative;width:130px;height:130px;margin:12px auto 24px;cursor:pointer}
.connect-core{position:absolute;inset:38px;border-radius:50%;background:rgba(167,139,250,.28);border:2px solid rgba(167,139,250,.7)}
.connect-ring{position:absolute;inset:0;border-radius:50%;border:2px solid rgba(167,139,250,.5);animation:ripple 2s ease-out infinite}
.connect-ring:nth-child(2){animation-delay:.55s}
.connect-ring:nth-child(3){animation-delay:1.1s}
@keyframes ripple{0%{transform:scale(.4);opacity:.85}100%{transform:scale(1.2);opacity:0}}
.online-dot{display:inline-block;width:8px;height:8px;background:#22c55e;border-radius:50%;margin-right:6px;animation:pulse 1.5s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
.bottom-filters{position:absolute;bottom:68px;left:0;right:0;padding:0 12px;display:flex;flex-direction:column;gap:8px}
.filter-row{display:flex;gap:8px}
.filter-chip{flex:1;background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.1);border-radius:14px;padding:11px;text-align:left;cursor:pointer}
.group-chip{background:rgba(167,139,250,.12);border:1px solid rgba(167,139,250,.35);border-radius:14px;padding:12px;text-align:center;cursor:pointer;color:#e9d5ff;font-weight:600}
.popup-bg{position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:200;display:none;align-items:flex-end;justify-content:center}
.popup{background:#1a1a2e;border-radius:20px 20px 0 0;padding:18px;width:100%;max-width:420px;max-height:80vh;overflow-y:auto}
.popup-opt{padding:13px;border-radius:12px;margin-bottom:7px;background:rgba(255,255,255,.05);text-align:center;cursor:pointer}
.call-screen{position:fixed;inset:0;background:#0a0618;z-index:50;display:none;flex-direction:column}
#remoteVideo{flex:1;width:100%;object-fit:cover;background:#111}
#localVideo{position:absolute;right:12px;top:52px;width:100px;height:140px;border-radius:12px;object-fit:cover;border:2px solid rgba(255,255,255,.25);background:#222;z-index:60}
.call-top{position:absolute;top:0;left:0;right:0;padding:12px 14px;display:flex;justify-content:space-between;z-index:70;background:linear-gradient(to bottom,rgba(0,0,0,.5),transparent)}
.call-bottom{position:absolute;bottom:0;left:0;right:0;padding:16px;display:flex;justify-content:center;gap:14px;z-index:70;background:linear-gradient(to top,rgba(0,0,0,.55),transparent)}
.ctrl-btn{width:54px;height:54px;border-radius:50%;border:none;color:#fff;font-weight:600;font-size:.7rem}
.ctrl-next{background:rgba(255,255,255,.15)}.ctrl-end{background:#dc2626}.ctrl-flip{background:rgba(96,165,250,.35)}
.finding-overlay{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;background:radial-gradient(circle at center,#1e1b4b,#0a0618 70%);z-index:55}
.finding-rings{position:relative;width:160px;height:160px;margin-bottom:20px}
.finding-rings .r{position:absolute;inset:0;border-radius:50%;border:2px solid rgba(167,139,250,.4);animation:findRipple 2.2s ease-out infinite}
.finding-rings .r:nth-child(2){animation-delay:.5s}.finding-rings .r:nth-child(3){animation-delay:1s}
.finding-rings .core{position:absolute;inset:50px;border-radius:50%;background:linear-gradient(135deg,rgba(167,139,250,.4),rgba(96,165,250,.3));display:flex;align-items:center;justify-content:center;font-size:1.8rem}
@keyframes findRipple{0%{transform:scale(.35);opacity:.9}100%{transform:scale(1.25);opacity:0}}
.menu-btn{width:36px;height:36px;border-radius:50%;background:rgba(0,0,0,.4);border:none;color:#fff;font-size:1.2rem}
.menu-dropdown{position:absolute;top:48px;right:14px;background:#1e1e32;border-radius:12px;padding:6px 0;min-width:140px;display:none;z-index:80}
.menu-dropdown button{display:block;width:100%;padding:12px 16px;background:none;border:none;color:#eee;text-align:left}
.link-btn{display:block;text-align:center;padding:12px;border-radius:12px;margin:10px 0;background:linear-gradient(90deg,#059669,#10b981);color:#fff;font-weight:600;text-decoration:none}
.step{display:flex;gap:10px;margin-bottom:8px;font-size:.84rem}
.step-num{min-width:22px;height:22px;border-radius:50%;background:linear-gradient(135deg,#7c3aed,#2563eb);display:flex;align-items:center;justify-content:center;font-size:.7rem;font-weight:700}
</style>
"""

ICONS = {
    "home":'<svg viewBox="0 0 24 24"><path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"/></svg>',
    "world":'<svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/></svg>',
    "client":'<svg viewBox="0 0 24 24"><path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z"/></svg>',
    "chat":'<svg viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H6l-2 2V4h16v12z"/></svg>',
    "favourite":'<svg viewBox="0 0 24 24"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/></svg>',
    "account":'<svg viewBox="0 0 24 24"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/></svg>',
}

def nav(active):
    items = [("home","home","/home"),("world","world","/world"),("client","client","/client"),
             ("chat","chat","/chat"),("favourite","favourite","/favourite"),("account","account","/account")]
    h = '<div class="bottom-nav">'
    for k, l, u in items:
        c = "nav-item active" if active == k else "nav-item"
        h += f'<a href="{u}" class="{c}">{ICONS[k]}<span>{t(l)}</span></a>'
    return h + "</div>"

AUTH = """
<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Limi</title>""" + CSS + """</head><body>
<div class="wrap">
  <div style="text-align:center;padding:20px 0 8px">
    <div class="logo" style="font-size:2rem">Limi</div>
    <p style="color:#94a3b8;font-size:.88rem;margin-top:4px">Verified 18+ • Safe Video Chat</p>
  </div>
  {% if error %}<div class="error">{{error}}</div>{% endif %}
  {% if success %}<div class="success">{{success}}</div>{% endif %}

  <div class="tabs">
    <div class="tab {% if mode=='signin' %}on{% endif %}" onclick="location='/?mode=signin'">Sign In</div>
    <div class="tab {% if mode=='signup' %}on{% endif %}" onclick="location='/?mode=signup'">Sign Up</div>
  </div>

  {% if mode=='signin' %}
  <div class="card">
    <form method="POST" action="/signin">
      <label>Username / Email / Mobile</label>
      <input name="login" required placeholder="username or email or phone">
      <label>Password</label>
      <input type="password" name="password" required>
      <button class="btn btn-primary" style="margin-top:14px">Sign In</button>
    </form>
  </div>
  {% else %}
  <div class="card">
    <div class="info">Pehli baar: Aadhaar ZIP se 18+ verify + account banao. Baad mein sirf password se login.</div>
    <form method="POST" action="/signup" enctype="multipart/form-data">
      <label>Aadhaar Offline ZIP</label>
      <input type="file" name="aadhaar_zip" accept=".zip" required>
      <label>Share Code</label>
      <input type="password" name="share_code" required placeholder="4-digit share code">
      <label>Username (unique)</label>
      <input name="username" required minlength="3" maxlength="20" pattern="[A-Za-z0-9_]+" placeholder="e.g. rahul_21">
      <label>Mobile OR Email (kam se kam ek)</label>
      <input name="phone" placeholder="10-digit mobile">
      <input name="email" type="email" placeholder="email@example.com" style="margin-top:8px">
      <label>Password</label>
      <input type="password" name="password" required minlength="6" placeholder="min 6 characters">
      <button class="btn btn-primary" style="margin-top:14px">Verify & Sign Up</button>
    </form>
    <div style="margin-top:18px;padding-top:14px;border-top:1px solid rgba(255,255,255,0.08)">
      <p style="font-size:0.85rem;color:#94a3b8;margin-bottom:10px;text-align:center">ZIP nahi hai? Pehle yahan se download karo</p>
      <a class="link-btn" href="https://myaadhaar.uidai.gov.in/offline-ekyc" target="_blank" rel="noopener">🔗 Offline e-KYC ZIP Download</a>
      <p style="font-size:0.85rem;color:#c4b5fd;margin:14px 0 8px;text-align:center">🎬 Video se samjho (kaise download kare)</p>
      <div style="border-radius:14px;overflow:hidden;background:#000;aspect-ratio:9/16;max-height:420px;margin:0 auto">
        <iframe src="https://www.youtube.com/embed/YesZxRc61-Q" title="How to download Offline e-KYC ZIP"
          style="width:100%;height:100%;min-height:320px;border:0"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          allowfullscreen></iframe>
      </div>
    </div>
  </div>
  {% endif %}
</div>
</body></html>
"""

HOME = """
<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Home</title>""" + CSS + """</head><body>
<div class="topbar"><div class="logo">Limi</div>
<div style="display:flex;align-items:center;gap:8px">
<div class="avatar">{%if pic%}<img src="{{pic}}">{%else%}{{name[0]|upper}}{%endif%}</div>
<div><div class="pname">{{username}}</div><div class="pstatus">{{verified}}</div>
<a href="/logout" class="logout-btn">{{logout}}</a></div></div></div>
<div class="home-hero">
  <div class="home-hello">Hey, {{name.split()[0]}} 👋</div>
  <span class="home-badge">✓ {{verified}}</span>
  {% if premium %}<span class="home-badge gold">⭐ Premium</span>{% endif %}
  <span class="home-badge">Lv {{level}}</span>
</div>
<div class="home-grid">
  <a class="home-tile" href="/world"><div style="font-size:1.6rem">🌍</div><div>World</div></a>
  <a class="home-tile" href="/account"><div style="font-size:1.6rem">✨</div><div>Profile</div></a>
</div>
<div class="card"><div style="color:#94a3b8;font-size:.85rem">Score</div>
<div style="font-size:1.2rem;font-weight:700">{{score}} pts · Level {{level}}</div>
<div class="level-bar"><div class="level-fill" style="width:{{level_pct}}%"></div></div></div>
{{nav|safe}}</body></html>
"""

SIMPLE = """
<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{title}}</title>""" + CSS + """</head><body>
<div class="topbar"><div class="logo">Limi</div></div>
<div style="text-align:center;padding:50px 16px;color:#888">{{title}} — {{msg}}</div>
{{nav|safe}}</body></html>
"""

WORLD = """
<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>World</title>""" + CSS + """</head><body>
<div class="topbar" id="mainTop"><div class="logo">Limi</div></div>
<div id="startScreen" style="position:relative;min-height:calc(100vh - 120px)">
  <div class="start-screen">
    <div style="font-size:1.25rem;font-weight:600">{{tap}}</div>
    <div style="color:#94a3b8;margin:8px 0 12px"><span class="online-dot"></span><span id="onlineNum">{{online_count}}</span> {{online}}</div>
    <p style="font-size:.72rem;color:#64748b;max-width:300px">Dono same site pe Random → Start almost ek saath dabao</p>
    <div class="connect-wrap" onclick="startMatch()">
      <div class="connect-ring"></div><div class="connect-ring"></div><div class="connect-ring"></div>
      <div class="connect-core"></div>
    </div>
  </div>
  <div class="bottom-filters">
    <div class="group-chip" onclick="openGroup()">👥 {{group}}</div>
    <div class="filter-row">
      <div class="filter-chip" onclick="openGender()"><b>🎯 <span id="genderLabel">{{all_g}}</span></b><div style="font-size:.7rem;color:#94a3b8">Girl/Guy/Random</div></div>
      <div class="filter-chip" onclick="openPrefs()"><b>⚙️ {{prefs}}</b><div style="font-size:.7rem;color:#94a3b8">Age</div></div>
    </div>
  </div>
</div>
<div class="popup-bg" id="genderPopup"><div class="popup">
  <h3 style="text-align:center;margin-bottom:10px">Gender</h3>
  <div class="popup-opt" onclick="trySetGender('F')">👩 {{girl}}</div>
  <div class="popup-opt" onclick="trySetGender('M')">👨 {{guy}}</div>
  <div class="popup-opt" onclick="trySetGender('BOTH')">🎲 {{random}} (Free)</div>
  <div class="popup-opt" style="color:#94a3b8" onclick="closePopups()">Cancel</div>
</div></div>
<div class="popup-bg" id="premiumPopup"><div class="popup" style="text-align:center">
  <h3>⭐ Premium ₹99/mo</h3>
  <p style="color:#94a3b8;font-size:.85rem;margin:10px 0">Only Girls/Guys filter unlock (demo)</p>
  <button class="btn btn-gold" onclick="buyPremium()">Activate Demo</button>
  <div class="popup-opt" style="color:#94a3b8;margin-top:8px" onclick="closePopups()">Not now</div>
</div></div>
<div class="popup-bg" id="prefsPopup"><div class="popup">
  <h3 style="text-align:center">{{prefs}}</h3>
  <label>{{age}}</label>
  <select id="ageMin"><option>18</option><option>20</option><option>22</option><option>25</option></select>
  <button class="btn btn-primary" style="margin-top:12px" onclick="closePopups()">{{apply}}</button>
</div></div>
<div class="popup-bg" id="groupPopup"><div class="popup">
  <h3 style="text-align:center">{{group}}</h3>
  <button class="btn btn-primary" onclick="createGroup()">{{create_g}}</button>
  <input id="joinCode" placeholder="CODE" style="margin-top:10px;text-transform:uppercase">
  <button class="btn btn-primary" style="margin-top:8px" onclick="joinGroup()">{{join_g}}</button>
  <div id="groupResult" style="display:none;margin-top:12px;text-align:center">
    <div id="gCode" style="font-size:1.5rem;letter-spacing:3px;font-weight:700"></div>
  </div>
  <div class="popup-opt" style="color:#94a3b8;margin-top:8px" onclick="closePopups()">Close</div>
</div></div>
<div class="call-screen" id="callScreen">
  <div class="finding-overlay" id="findingUI">
    <div class="finding-rings"><div class="r"></div><div class="r"></div><div class="r"></div><div class="core">✨</div></div>
    <div id="statusText" style="font-weight:600;color:#e9d5ff">{{finding}}</div>
  </div>
  <video id="remoteVideo" autoplay playsinline style="display:none"></video>
  <video id="localVideo" autoplay playsinline muted></video>
  <div class="call-top">
    <div id="topStatus" style="color:#fff"></div>
    <div style="position:relative">
      <button class="menu-btn" onclick="toggleMenu()">⋯</button>
      <div class="menu-dropdown" id="menuDrop">
        <button onclick="doReport()">🚩 {{report}}</button>
        <button onclick="doBlock()">🚫 {{block}}</button>
      </div>
    </div>
  </div>
  <div class="call-bottom">
    <button class="ctrl-btn ctrl-flip" onclick="flipCamera()">🔄</button>
    <button class="ctrl-btn ctrl-next" onclick="nextMatch()">{{next}}</button>
    <button class="ctrl-btn ctrl-end" onclick="stopMatch()">{{end}}</button>
  </div>
</div>
{{nav|safe}}
<script>
let localStream=null,pc=null,roomId=null,isInitiator=false,pollTimer=null,mySid=null,matching=false,wantGender="BOTH",facingMode="user";
const isGirl={{ 'true' if is_girl else 'false' }}, isPremium={{ 'true' if premium else 'false' }};
const ice={iceServers:[{urls:"stun:stun.l.google.com:19302"},{urls:"stun:stun1.l.google.com:19302"}]};
function $(id){return document.getElementById(id)}
function openGender(){$("genderPopup").style.display="flex"}
function openPrefs(){$("prefsPopup").style.display="flex"}
function openGroup(){$("groupPopup").style.display="flex"}
function openPremium(){$("premiumPopup").style.display="flex"}
function closePopups(){["genderPopup","prefsPopup","groupPopup","premiumPopup"].forEach(i=>$ (i).style.display="none")}
function trySetGender(g){
  if((g==="F"||g==="M")&&!isGirl&&!isPremium){closePopups();openPremium();return}
  wantGender=g; $("genderLabel").innerText={F:"{{girl}}",M:"{{guy}}",BOTH:"{{random}}"}[g]; closePopups();
}
function toggleMenu(){const m=$("menuDrop");m.style.display=m.style.display==="block"?"none":"block"}
async function buyPremium(){const r=await fetch("/premium/buy",{method:"POST"});if((await r.json()).ok)location.reload()}
async function createGroup(){const d=await(await fetch("/group/create",{method:"POST"})).json();if(d.code){$("gCode").innerText=d.code;$("groupResult").style.display="block"}}
async function joinGroup(){const code=($("joinCode").value||"").toUpperCase();const d=await(await fetch("/group/join",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({code})})).json();alert(d.ok?"Joined":(d.error||"Fail"));closePopups()}
async function startMatch(){
  if(matching)return;
  if((wantGender==="F"||wantGender==="M")&&!isGirl&&!isPremium){openPremium();return}
  matching=true;$("startScreen").style.display="none";$("mainTop").style.display="none";
  document.querySelector(".bottom-nav").style.display="none";
  $("callScreen").style.display="flex";$("findingUI").style.display="flex";$("remoteVideo").style.display="none";
  await startCam();
  const data=await(await fetch("/match",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({want:wantGender})})).json();
  if(data.error==="premium"){matching=false;stopMatch();openPremium();return}
  mySid=data.sid;
  if(data.matched){roomId=data.room;isInitiator=true;onConnected();await setupPeer(true);startPoll()}
  else pollForMatch();
}
async function pollForMatch(){
  if(!matching)return;
  try{const data=await(await fetch("/match/status?sid="+mySid)).json();
    if(data.matched){roomId=data.room;isInitiator=true;onConnected();await setupPeer(true);startPoll();return}
    if(data.online!=null)$("onlineNum").innerText=data.online;
  }catch(e){}
  setTimeout(pollForMatch,1200);
}
function onConnected(){$("findingUI").style.display="none";$("remoteVideo").style.display="block";$("topStatus").innerText="{{connected}}";fetch("/stats/talk",{method:"POST"})}
async function startCam(){
  try{if(localStream)localStream.getTracks().forEach(t=>t.stop());
    localStream=await navigator.mediaDevices.getUserMedia({video:{facingMode},audio:true});
    $("localVideo").srcObject=localStream;
    if(pc){const s=pc.getSenders().find(x=>x.track&&x.track.kind==="video");if(s)s.replaceTrack(localStream.getVideoTracks()[0])}
  }catch(e){alert("Camera: "+e.message)}
}
async function flipCamera(){facingMode=facingMode==="user"?"environment":"user";await startCam()}
async function setupPeer(init){
  pc=new RTCPeerConnection(ice);
  if(localStream)localStream.getTracks().forEach(t=>pc.addTrack(t,localStream));
  pc.ontrack=e=>{$("remoteVideo").srcObject=e.streams[0];onConnected()};
  pc.onicecandidate=e=>{if(e.candidate)sendSig({type:"candidate",candidate:e.candidate})};
  if(init){const o=await pc.createOffer();await pc.setLocalDescription(o);sendSig({type:"offer",sdp:o})}
}
function sendSig(data){fetch("/signal",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({room:roomId,data,from:isInitiator?"a":"b"})})}
function startPoll(){pollTimer=setInterval(async()=>{try{const list=await(await fetch("/signal?room="+roomId+"&me="+(isInitiator?"a":"b"))).json();for(const m of list)await handleSig(m)}catch(e){}},900)}
async function handleSig(msg){
  if(!pc)return;
  if(msg.type==="offer"&&!isInitiator){await pc.setRemoteDescription(new RTCSessionDescription(msg.sdp));const a=await pc.createAnswer();await pc.setLocalDescription(a);sendSig({type:"answer",sdp:a})}
  else if(msg.type==="answer"&&isInitiator)await pc.setRemoteDescription(new RTCSessionDescription(msg.sdp));
  else if(msg.type==="candidate"){try{await pc.addIceCandidate(new RTCIceCandidate(msg.candidate))}catch(e){}}
}
function cleanup(){if(pollTimer)clearInterval(pollTimer);pollTimer=null;if(pc){pc.close();pc=null}if(localStream){localStream.getTracks().forEach(t=>t.stop());localStream=null}
  $("localVideo").srcObject=null;$("remoteVideo").srcObject=null;roomId=null}
function stopMatch(){matching=false;cleanup();fetch("/match/leave",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({sid:mySid})});
  $("callScreen").style.display="none";$("startScreen").style.display="block";$("mainTop").style.display="flex";document.querySelector(".bottom-nav").style.display="flex";refreshOnline()}
function nextMatch(){cleanup();matching=false;fetch("/match/leave",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({sid:mySid})});setTimeout(startMatch,300)}
function doReport(){fetch("/report",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({room:roomId})});$("menuDrop").style.display="none";nextMatch()}
function doBlock(){fetch("/report",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({room:roomId,block:true})});$("menuDrop").style.display="none";nextMatch()}
async function refreshOnline(){try{await fetch("/heartbeat",{method:"POST"});const d=await(await fetch("/online")).json();$("onlineNum").innerText=d.count||0}catch(e){}}
setInterval(refreshOnline,4000);refreshOnline();
</script></body></html>
"""

ACCOUNT = """
<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Account</title>""" + CSS + """</head><body>
<div class="topbar"><div class="logo">Limi</div></div>
<div class="wrap">
<div class="card" style="text-align:center">
<div class="avatar" style="width:72px;height:72px;margin:0 auto 8px;font-size:1.6rem">{%if pic%}<img src="{{pic}}">{%else%}{{name[0]|upper}}{%endif%}</div>
<div style="font-weight:600">{{name}}</div>
<div style="color:#94a3b8;font-size:.8rem">@{{username}}</div>
<div style="color:#4ade80;font-size:.8rem;margin-top:4px">{{verified}} · Lv {{level}}</div>
</div>
<div class="card">
<form method="POST" enctype="multipart/form-data">
<label>{{upload_photo}}</label><input type="file" name="photo" accept="image/*">
<button class="btn btn-primary" name="action" value="photo" style="margin-top:10px">{{save}}</button>
</form></div>
<div class="card">
<form method="POST"><label>{{select_lang}}</label>
<select name="lang"><option value="en">English</option><option value="hi" {%if lang=='hi'%}selected{%endif%}>हिन्दी</option></select>
<button class="btn btn-primary" name="action" value="lang" style="margin-top:10px">{{save}}</button>
</form></div>
</div>{{nav|safe}}</body></html>
"""

def require_login():
    if not session.get("user_id"):
        return redirect("/")
    return None

@app.route("/")
def index():
    if session.get("user_id"):
        return redirect("/home")
    mode = request.args.get("mode", "signin")
    if mode not in ("signin", "signup"):
        mode = "signin"
    return render_template_string(AUTH, mode=mode, error=None, success=None)

@app.route("/signin", methods=["POST"])
def signin():
    login = (request.form.get("login") or "").strip()
    password = request.form.get("password") or ""
    u = user_by_login(login)
    if not u or not check_pw(password, u["pass_hash"]):
        return render_template_string(AUTH, mode="signin", error="Galat login ya password", success=None)
    load_session_user(u)
    return redirect("/home")

@app.route("/signup", methods=["POST"])
def signup():
    zf = request.files.get("aadhaar_zip")
    code = (request.form.get("share_code") or "").strip()
    username = (request.form.get("username") or "").strip().lower()
    phone = re.sub(r"\D", "", request.form.get("phone") or "")
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""

    if not zf or not code:
        return render_template_string(AUTH, mode="signup", error="ZIP + Share Code zaroori", success=None)
    if len(username) < 3 or not re.match(r"^[a-z0-9_]+$", username):
        return render_template_string(AUTH, mode="signup", error="Username: 3+ letters/numbers/_", success=None)
    if len(password) < 6:
        return render_template_string(AUTH, mode="signup", error="Password min 6 characters", success=None)
    if not phone and not email:
        return render_template_string(AUTH, mode="signup", error="Mobile ya Email mein se ek do", success=None)

    if q("SELECT 1 AS x FROM users WHERE username=?", (username,), fetchone=True):
        return render_template_string(AUTH, mode="signup", error="Username already taken", success=None)

    xml, err = extract_xml(zf.read(), code)
    if err:
        return render_template_string(AUTH, mode="signup", error=err, success=None)

    sig_ok, sig_code, sig_msg = verify_uidai_signature(xml)
    if not sig_ok:
        return render_template_string(AUTH, mode="signup", error=sig_msg, success=None)

    data = parse_xml(xml)
    if not data:
        return render_template_string(AUTH, mode="signup", error=(
            "You are not eligible for Limi. ZIP se name/DOB read nahi hua. "
            "Galat Share Code ya edited/corrupt file ho sakti hai."
        ), success=None)

    age = age_from(data["dob"])
    if age is not None and age < 18:
        return render_template_string(AUTH, mode="signup", error=(
            f"You are not eligible for Limi. "
            f"Aapki age {age} saal hai. Limi sirf 18+ verified users ke liye hai. "
            f"18 se kam age wale register nahi kar sakte."
        ), success=None)
    if age is None:
        return render_template_string(AUTH, mode="signup", error=(
            "You are not eligible for Limi. "
            "Date of birth ZIP se verify nahi ho payi. Fresh official Offline e-KYC ZIP use karo."
        ), success=None)

    ref = (data.get("reference_id") or "").strip()
    g = (data.get("gender") or "").upper()
    gender = "M" if g.startswith("M") else ("F" if g.startswith("F") else "")

    if ref and q("SELECT 1 AS x FROM users WHERE ref_id=?", (ref,), fetchone=True):
        return render_template_string(AUTH, mode="signup", error="Ye Aadhaar ZIP pehle se registered hai", success=None)

    try:
        if USE_PG:
            row = q(
                """INSERT INTO users(username,email,phone,pass_hash,name,gender,ref_id,created)
                   VALUES(?,?,?,?,?,?,?,?) RETURNING id""",
                (username, email or None, phone or None, hash_pw(password), data["name"], gender, ref or None, time.time()),
                fetchone=True, commit=True
            )
            uid = row["id"]
        else:
            q(
                """INSERT INTO users(username,email,phone,pass_hash,name,gender,ref_id,created)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (username, email or None, phone or None, hash_pw(password), data["name"], gender, ref or None, time.time()),
                commit=True
            )
            row = q("SELECT last_insert_rowid() AS id", fetchone=True)
            uid = row["id"] if isinstance(row, dict) else row[0]
        u = user_by_id(uid)
    except Exception as e:
        msg = str(e).lower()
        if "unique" in msg or "duplicate" in msg or "integrity" in msg:
            return render_template_string(AUTH, mode="signup", error="Username/Aadhaar already used", success=None)
        return render_template_string(AUTH, mode="signup", error="Signup error: "+str(e)[:120], success=None)

    load_session_user(u)
    return redirect("/home")

@app.route("/home")
def home():
    if not session.get("user_id"):
        return redirect("/")
    score = session.get("score", 0)
    level = level_from_score(score)
    return render_template_string(HOME, name=session["name"], username=session.get("username",""),
        pic=session.get("pic"), verified=t("verified"), logout=t("logout"), nav=nav("home"),
        premium=is_premium(), level=level, score=score, level_pct=min(100, (score % 50) * 2))

@app.route("/world")
def world():
    if not session.get("user_id"):
        return redirect("/")
    online = online_count()[0]
    return render_template_string(WORLD, tap=t("tap"), online=t("online"), online_count=online,
        girl=t("girl"), guy=t("guy"), random=t("random"), prefs=t("prefs"), age=t("age"),
        apply=t("apply"), all_g=t("all_g"), finding=t("finding"), connected=t("connected"),
        next=t("next"), report=t("report"), block=t("block"), end=t("end"),
        group=t("group"), create_g=t("create_g"), join_g=t("join_g"),
        is_girl=is_girl(), premium=is_premium(), nav=nav("world"))

@app.route("/client")
def client():
    if not session.get("user_id"): return redirect("/")
    return render_template_string(SIMPLE, title=t("client"), msg=t("coming"), nav=nav("client"))

@app.route("/chat")
def chat():
    if not session.get("user_id"): return redirect("/")
    return render_template_string(SIMPLE, title=t("chat"), msg=t("chat_soon"), nav=nav("chat"))

@app.route("/favourite")
def favourite():
    if not session.get("user_id"): return redirect("/")
    return render_template_string(SIMPLE, title=t("favourite"), msg=t("coming"), nav=nav("favourite"))

@app.route("/account", methods=["GET", "POST"])
def account():
    if not session.get("user_id"): return redirect("/")
    if request.method == "POST":
        act = request.form.get("action")
        if act == "lang":
            session["lang"] = request.form.get("lang", "en")
            q("UPDATE users SET lang=? WHERE id=?", (session["lang"], session["user_id"]), commit=True)
        elif act == "photo":
            ph = request.files.get("photo")
            if ph and ph.filename:
                try:
                    d = ph.read()
                    if len(d) < 1500000:
                        b64 = base64.b64encode(d).decode()
                        ext = "png" if ph.filename.lower().endswith(".png") else "jpeg"
                        session["pic"] = f"data:image/{ext};base64,{b64}"
                        q("UPDATE users SET pic=? WHERE id=?", (session["pic"], session["user_id"]), commit=True)
                except Exception:
                    pass
    score = session.get("score", 0)
    return render_template_string(ACCOUNT, name=session["name"], username=session.get("username",""),
        pic=session.get("pic"), verified=t("verified"), likes=t("likes"),
        upload_photo=t("upload_photo"), select_lang=t("select_lang"), save=t("save"),
        lang=session.get("lang","en"), level=level_from_score(score), nav=nav("account"))

@app.route("/logout")
def logout():
    sid = session.get("sid")
    if sid:
        waiting_leave(sid)
    session.clear()
    return redirect("/")

@app.route("/premium/buy", methods=["POST"])
def premium_buy():
    if not session.get("user_id"): return jsonify({"ok": False}), 401
    if is_girl(): return jsonify({"ok": False, "error": "Girls free"})
    until = datetime.datetime.utcnow() + datetime.timedelta(days=30)
    session["premium_until"] = until.isoformat()
    q("UPDATE users SET premium_until=? WHERE id=?", (until.isoformat(), session["user_id"]), commit=True)
    global CREDIT_POOL
    CREDIT_POOL += 99
    return jsonify({"ok": True})

@app.route("/stats/talk", methods=["POST"])
def stats_talk():
    if not session.get("user_id"): return jsonify({"ok": False})
    session["score"] = session.get("score", 0) + 5
    q("UPDATE users SET score=score+5, talks=talks+1 WHERE id=?", (session["user_id"],), commit=True)
    return jsonify({"ok": True})

@app.route("/online")
def online():
    count, w = online_count()
    return jsonify({"count": count, "waiting": w})

@app.route("/heartbeat", methods=["POST"])
def heartbeat():
    if not session.get("user_id"): return jsonify({"ok": False})
    sid = session.get("sid") or str(uuid.uuid4())[:12]
    session["sid"] = sid
    n = presence_ping(sid, session.get("name",""), session.get("gender",""), session.get("user_id"))
    return jsonify({"ok": True, "online": n})

@app.route("/match", methods=["POST"])
def match():
    if not session.get("user_id"): return jsonify({"error": "auth"}), 401
    body = request.get_json(force=True, silent=True) or {}
    want = (body.get("want") or "BOTH").upper()
    if want not in ("BOTH", "M", "F"): want = "BOTH"
    if not can_use_filter(want):
        return jsonify({"error": "premium"})
    my_gender = session.get("gender") or ""
    sid = session.get("sid") or str(uuid.uuid4())[:12]
    session["sid"] = sid
    presence_ping(sid, session["name"], my_gender, session["user_id"])
    partner, room = find_match_db(sid, my_gender, want)
    if partner:
        return jsonify({"matched": True, "room": room, "initiator": True, "sid": sid})
    waiting_add(sid, session["name"], my_gender, want, session["user_id"])
    return jsonify({"matched": False, "sid": sid, "online": online_count()[0]})

@app.route("/match/status")
def match_status():
    sid = request.args.get("sid")
    count, _ = online_count()
    if not sid:
        return jsonify({"matched": False, "online": count})
    me = q("SELECT * FROM waiting WHERE sid=?", (sid,), fetchone=True)
    if not me:
        return jsonify({"matched": False, "online": count})
    partner, room = find_match_db(sid, me["gender"], me["want"])
    if partner:
        return jsonify({"matched": True, "room": room, "initiator": True, "online": count})
    return jsonify({"matched": False, "online": online_count()[0]})

@app.route("/match/leave", methods=["POST"])
def match_leave():
    body = request.get_json(force=True, silent=True) or {}
    sid = body.get("sid") or session.get("sid")
    if sid:
        waiting_leave(sid)
    return jsonify({"ok": True})

@app.route("/group/create", methods=["POST"])
def group_create():
    if not session.get("user_id"): return jsonify({"error": "auth"}), 401
    code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    GROUPS[code] = {"admin": session["name"], "members": [session["name"]], "created": time.time()}
    return jsonify({"code": code})

@app.route("/group/join", methods=["POST"])
def group_join():
    if not session.get("user_id"): return jsonify({"error": "auth"}), 401
    body = request.get_json(force=True, silent=True) or {}
    code = (body.get("code") or "").upper()
    if code not in GROUPS:
        return jsonify({"ok": False, "error": "Invalid code"})
    g = GROUPS[code]
    if len(g["members"]) >= 10:
        return jsonify({"ok": False, "error": "Full"})
    if session["name"] not in g["members"]:
        g["members"].append(session["name"])
    return jsonify({"ok": True})

@app.route("/report", methods=["POST"])
def report():
    body = request.get_json(force=True, silent=True) or {}
    key = body.get("room") or "x"
    REPORTS[key] = REPORTS.get(key, 0) + 1
    if body.get("block") or REPORTS[key] >= 3:
        BANNED.add(key)
    return jsonify({"ok": True})

@app.route("/signal", methods=["GET", "POST"])
def signal():
    if request.method == "POST":
        body = request.get_json(force=True, silent=True) or {}
        room = (body.get("room") or "").upper()
        data = body.get("data")
        frm = body.get("from", "a")
        if not room or not data:
            return jsonify({"ok": False})
        if room not in ROOMS:
            ROOMS[room] = []
        ROOMS[room].append({"to": "b" if frm == "a" else "a", "data": data})
        ROOMS[room] = ROOMS[room][-25:]
        return jsonify({"ok": True})
    room = (request.args.get("room") or "").upper()
    me = request.args.get("me", "a")
    if room not in ROOMS:
        return jsonify([])
    mine = [m["data"] for m in ROOMS[room] if m["to"] == me]
    ROOMS[room] = [m for m in ROOMS[room] if m["to"] != me]
    return jsonify(mine)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("Limi on", port, "DB:", DB_PATH)
    app.run(debug=False, host="0.0.0.0", port=port)
