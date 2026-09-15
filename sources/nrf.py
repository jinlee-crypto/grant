"""한국연구재단 사업공고(신규사업공모) — 목록에 접수일자·상태 제공."""
import re
from datetime import date
from .base import Fetcher, soup, clean, norm_date

NAME = "한국연구재단"
BASE = "https://www.nrf.re.kr"
LIST = BASE + "/page/362"
VIEW = BASE + "/biz/notice/view"


def _months_back(n):
    t = date.today()
    y, m = t.year, t.month - n
    while m <= 0:
        y, m = y - 1, m + 12
    return y, m


def parse_list(html):
    sp = soup(html)
    out = []
    for b in sp.select(".public-notice-block"):
        a = b.select_one("a.view_btn")
        if not a:
            continue
        txt = clean(b.get_text(" "))
        dates = re.findall(r"\d{4}-\d{2}-\d{2}", txt.split("접수일자", 1)[-1]) if "접수일자" in txt else []
        st = [clean(x.get_text()) for x in b.select(".pnb-state .block-text")]
        bc = b.select_one(".bread-crumb-text")
        out.append(dict(src_id=a["data-post_no"], _biz=a.get("data-biz_no", "0"), title=clean(a.get_text()),
                        ministry="", agency="한국연구재단",
                        category=clean(b.select_one(".title-category").get_text()) if b.select_one(".title-category") else "",
                        program=clean(bc.get_text()).strip("[]") if bc else "",
                        status=next((s for s in st if not s.startswith("D")), ""),
                        rcv_start=dates[0] if dates else "", rcv_end=dates[1] if len(dates) > 1 else "",
                        end_estimated=0))
    tot = sp.select_one(".nums-total")
    return out, int(clean(tot.get_text())) if tot and clean(tot.get_text()).isdigit() else 1


def parse_detail(html):
    sp = soup(html)
    c = sp.select_one(".cms-contents") or sp.body
    txt = clean(c.get_text(" "))
    reg = re.search(r"등록일\s*:\s*(\d{4}-\d{2}-\d{2})", txt)
    mini = re.search(r"<주무부처>\s*(?:부총리 겸\s*)?(\S+?부|\S+?처|\S+?청)\s", txt)
    body = txt.split("공고내용", 1)[-1] if "공고내용" in txt else txt
    return dict(posted=reg.group(1) if reg else "", ministry=mini.group(1) if mini else "",
                body_text=body[:20000])


def collect(f: Fetcher, known, months=3, max_pages=10, log=print):
    y0, m0 = _months_back(months)
    t = date.today()
    base = dict(menuNo=362, bizNotGubn="guide", searchRegChoiceDttm="D", bizSearchRegDttmAllYn="N",
                regStartDttm=f"{y0}-{m0:02d}-01", regEndDttm=t.isoformat(),
                orderType="REG_DTTM", orderTypeAt="DESC")
    page, pages = 1, 1
    while page <= min(pages, max_pages):
        items, pages = parse_list(f.get(LIST, **base, pageNum=page))
        log(f"  연구재단 {page}/{pages}p {len(items)}건")
        for it in items:
            it["url"] = f"{VIEW}?ac=view&menuNo=362&postNo={it['src_id']}&bizNo={it['_biz']}"
            if known(it["src_id"]) is None:
                try:
                    it.update({k: v for k, v in parse_detail(f.get(it["url"])).items() if v})
                except Exception as e:
                    log(f"    상세 실패 {it['src_id']}: {e}")
            yield it
        page += 1
