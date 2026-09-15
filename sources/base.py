"""출처 공통 도구: HTTP 세션, 텍스트 정리, 마감일 추출."""
import re
import time
from datetime import date

import requests
from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (JNUH-BRI grant dashboard; contact: 의생명연구원)"
DELAY = 0.7


class Fetcher:
    def __init__(self, delay=DELAY):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = UA
        self.delay = delay

    def get(self, url, **params):
        time.sleep(self.delay)
        r = self.s.get(url, params=params or None, timeout=30)
        r.raise_for_status()
        r.encoding = r.apparent_encoding if r.encoding in (None, "ISO-8859-1") else r.encoding
        return r.text

    def post(self, url, data):
        time.sleep(self.delay)
        r = self.s.post(url, data=data, timeout=30)
        r.raise_for_status()
        return r.text


def soup(html):
    return BeautifulSoup(html, "html.parser")


def clean(s):
    return re.sub(r"\s+", " ", s or "").strip()


def norm_date(s):
    """'2026.9.3', '2026-09-03 18:00', '2026년 9월 3일' → '2026-09-03' (시각은 유지하지 않음)."""
    m = re.search(r"(20\d{2})\s*[.\-/년]\s*(\d{1,2})\s*[.\-/월]\s*(\d{1,2})", s or "")
    if not m:
        return ""
    y, mo, d = map(int, m.groups())
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return ""


_FULL = r"20\d{2}\s*[.\-/년]\s*\d{1,2}\s*[.\-/월]\s*\d{1,2}\s*일?"
_KEY = r"(접수\s*기간|신청\s*기간|접수\s*일자|공모\s*기간|제출\s*기한|접수\s*마감|신청\s*마감|마감\s*일?|제출\s*기간|모집\s*기간)"


def extract_period(text, posted=""):
    """본문/제목에서 (시작, 마감) 추정. 못 찾으면 ('','')."""
    t = clean(text)
    # 1) 키워드 뒤 '날짜 ~ 날짜'
    m = re.search(_KEY + r"[^0-9]{0,15}(" + _FULL + r")[^~\-–]{0,20}[~\-–]\s*[^0-9]{0,5}(" + _FULL + r"|\d{1,2}\s*[.\/월]\s*\d{1,2})", t)
    if m:
        start = norm_date(m.group(2))
        end = norm_date(m.group(3)) or _md_to_date(m.group(3), start)
        if end:
            return start, end
    # 2) 키워드 뒤 단일 날짜 (마감)
    m = re.search(_KEY + r"[^0-9]{0,15}(" + _FULL + r")", t)
    if m and re.search("마감|기한", m.group(1)):
        return "", norm_date(m.group(2))
    # 3) 제목 괄호형 '(9월 28일(월) 18시까지)', '~10.14.'
    m = re.search(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일.{0,15}?까지", t) or \
        re.search(r"~\s*(\d{1,2})\s*[./]\s*(\d{1,2})\.?\s*[\(（]?", t[:200])
    if m:
        return "", _md_to_date(f"{m.group(1)}월 {m.group(2)}", posted)
    # 4) 키워드 없는 '날짜 ~ 날짜' (첫 번째)
    m = re.search("(" + _FULL + r")\s*(?:\d{1,2}:\d{2})?\s*[~–]\s*(" + _FULL + ")", t)
    if m:
        return norm_date(m.group(1)), norm_date(m.group(2))
    return "", ""


def _md_to_date(s, ref):
    """'10.14' / '10월 14' 를 기준일(ref) 연도로 보정."""
    m = re.search(r"(\d{1,2})\s*[.\/월]\s*(\d{1,2})", s or "")
    if not m:
        return ""
    ref_d = date.fromisoformat(ref) if ref else date.today()
    mo, d = int(m.group(1)), int(m.group(2))
    y = ref_d.year + (1 if mo < ref_d.month - 6 else 0)
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return ""
