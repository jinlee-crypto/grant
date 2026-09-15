"""IRIS 범부처통합연구지원시스템 — 구조화된 접수기간 제공."""
import re
from .base import Fetcher, soup, clean, norm_date

NAME = "IRIS"
BASE = "https://www.iris.go.kr"
LIST = BASE + "/contents/retrieveBsnsAncmBtinSituListView.do"
VIEW = BASE + "/contents/retrieveBsnsAncmView.do"
STATUS = {"ancmPre": "접수예정", "ancmIng": "접수중"}


def _status(raw):
    if "마감" in raw:
        return "마감"
    if "예정" in raw:
        return "접수예정"
    if "접수" in raw:
        return "접수중"
    return ""


def parse_list(html, prg):
    sp = soup(html)
    out = []
    for li in sp.select("ul.dbody > li"):
        a = li.select_one("strong.title a")
        m = a and re.search(r"view\('(\d+)'", a.get("onclick", ""))
        if not m:
            continue
        inst = clean(li.select_one(".inst_title").get_text()) if li.select_one(".inst_title") else ""
        ministry, _, agency = inst.partition(">")
        info = {}
        for s in li.select(".etc_info span"):
            em = s.find("em")
            if em:
                k = clean(em.get_text()).rstrip(":").strip()
                em.extract()
                info[k] = clean(s.get_text())
        raw = info.get("공고상태", "")
        out.append(dict(src_id=m.group(1), title=clean(a.get_text()), ministry=clean(ministry),
                        agency=clean(agency), ancm_no=info.get("공고번호", ""),
                        posted=norm_date(info.get("공고일자", "")), category=info.get("공모유형", ""),
                        status=_status(raw) or STATUS.get(prg, prg), _raw_status=raw, url=LIST, _prg=prg))
    pages = 1
    cp = sp.select_one(".current_page")
    if cp and re.search(r"/\s*(\d+)", cp.get_text()):
        pages = int(re.search(r"/\s*(\d+)", cp.get_text()).group(1))
    return out, pages


def parse_detail(html):
    sp = soup(html)
    kv = {}
    for li in sp.select(".title_area ul.list_dot > li"):
        st, s = li.find("strong"), li.find("span", recursive=False)
        if st and s:
            kv[clean(st.get_text())] = clean(s.get_text(" "))
    dates = re.findall(r"\d{4}-\d{2}-\d{2}", kv.get("접수기간", ""))
    body = sp.select_one(".tb_contents .se-contents") or sp.select_one(".tb_contents")
    return dict(rcv_start=dates[0] if dates else "", rcv_end=dates[1] if len(dates) > 1 else "",
                end_estimated=0, contact=kv.get("사업담당자연락처", ""),
                body_text=clean(body.get_text(" "))[:20000] if body else "")


def collect(f: Fetcher, known, max_pages=8, log=print):
    f.get(LIST)  # 세션 쿠키 확보 (없으면 서버가 상태 필터를 무시하고 전체 공고를 돌려줌)
    for prg in STATUS:
        page, pages, empty_run = 1, 1, 0
        while page <= min(pages, max_pages):
            items, pages = parse_list(f.post(LIST, {"ancmPrg": prg, "pageIndex": page}), prg)
            if pages > 50:  # 필터가 안 먹은 응답 → 목록 상태값으로 걸러내고 페이지 수 제한
                pages = max_pages
            keep = [it for it in items if it["status"] != "마감"]
            log(f"  IRIS {STATUS[prg]} {page}p: {len(items)}건 중 {len(keep)}건 사용")
            empty_run = 0 if keep else empty_run + 1
            if empty_run >= 2:
                break
            for it in keep:
                k = known(it["src_id"])
                if k is None or not k["rcv_end"] or k["status"] != it["status"]:
                    try:
                        it.update(parse_detail(f.post(VIEW, {"ancmId": it["src_id"], "ancmPrg": prg})))
                    except Exception as e:
                        log(f"    상세 실패 {it['src_id']}: {e}")
                yield it
            page += 1
