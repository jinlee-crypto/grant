"""HT Dream (보건의료기술종합정보시스템, KHIDI) — 목록에 공고기간 제공."""
import re
from .base import Fetcher, soup, clean, norm_date

NAME = "HT Dream"
BASE = "https://www.htdream.kr"
LIST = BASE + "/main/pubAmt/PubAmtList.do"
VIEW = BASE + "/main/pubAmt/addPubAmtView2.do"


def parse_list(html):
    out = []
    for tr in soup(html).select("table tbody tr"):
        a = tr.select_one("a[onclick*=fn_select2]")
        tds = tr.find_all("td")
        if not a or len(tds) < 4:
            continue
        m = re.search(r"fn_select2\('(\d+)'\s*,\s*'(\w)'", a["onclick"])
        period = re.findall(r"\d{4}-\d{2}-\d{2}", tds[3].get_text())
        out.append(dict(src_id=m.group(1), _open=m.group(2), title=clean(a.get_text()),
                        ministry="보건복지부", agency="한국보건산업진흥원",
                        rcv_start=period[0] if period else "", rcv_end=period[1] if len(period) > 1 else "",
                        posted=period[0] if period else "", end_estimated=0, url=BASE + "/main/pubAmt/PubAmtList.do"))
    return out


def parse_detail(html):
    sp = soup(html)
    kv = {clean(th.get_text()): clean(th.find_next_sibling("td").get_text(" "))
          for th in sp.select("table.board th") if th.find_next_sibling("td")}
    body = sp.select_one("table.board .se-contents")
    return dict(ancm_no=kv.get("공고번호", ""),
                rcv_start=norm_date(kv.get("공고시작일", "")), rcv_end=norm_date(kv.get("공고종료일", "")),
                body_text=clean(body.get_text(" "))[:20000] if body else "")


def collect(f: Fetcher, known, pages=2, log=print):
    for p in range(1, pages + 1):
        items = parse_list(f.post(LIST, {"pageIndex": p, "pageUnit": 15}))
        log(f"  HT Dream {p}p {len(items)}건")
        for it in items:
            if known(it["src_id"]) is None:
                try:
                    it.update({k: v for k, v in parse_detail(
                        f.post(VIEW, {"pbanId": it["src_id"], "pbanOpenYn": it["_open"], "actionMode": "view"})).items() if v})
                except Exception as e:
                    log(f"    상세 실패 {it['src_id']}: {e}")
            yield it
