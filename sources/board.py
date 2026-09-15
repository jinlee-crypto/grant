"""일반 게시판형 출처(KHIDI, NECA, KEITI) — 마감일은 제목/본문에서 추정."""
import re
from urllib.parse import urljoin, urlparse, parse_qs
from .base import Fetcher, soup, clean, norm_date, extract_period


class Board:
    NAME = ""
    AGENCY = ""
    MINISTRY = ""
    LISTS = []          # [(url, params), ...]
    PAGES = 2

    def rows(self, sp, list_url):  # -> [(src_id, title, posted, url)]
        raise NotImplementedError

    def body(self, sp):
        raise NotImplementedError

    def collect(self, f: Fetcher, known, log=print):
        for url, params in self.LISTS:
            for p in range(1, self.PAGES + 1):
                html = f.get(url, **params, **self.page_param(p))
                rows = self.rows(soup(html), url)
                log(f"  {self.NAME} {p}p {len(rows)}건")
                for sid, title, posted, durl in rows:
                    it = dict(src_id=sid, title=title, posted=posted, url=durl,
                              agency=self.AGENCY, ministry=self.MINISTRY)
                    k = known(sid)
                    if k is None:
                        try:
                            it["body_text"] = self.body(soup(f.get(durl)))[:20000]
                        except Exception as e:
                            log(f"    상세 실패 {sid}: {e}")
                            it["body_text"] = ""
                        s, e_ = extract_period(title + " " + it["body_text"], posted)
                        it.update(rcv_start=s, rcv_end=e_, end_estimated=1 if e_ else 0)
                    yield it

    def page_param(self, p):
        return {"pageIndex": p}


class KHIDI(Board):
    NAME, AGENCY, MINISTRY = "KHIDI", "한국보건산업진흥원", "보건복지부"
    BASE = "https://www.khidi.or.kr"
    LISTS = [(BASE + "/board", {"menuId": "MENU01108"})]

    def page_param(self, p):
        return {"pageNum": p, "rowCnt": 10}

    def rows(self, sp, list_url):
        out, seen = [], set()
        for tr in sp.select("table.tstyle_list tbody tr"):
            a = tr.select_one("td.ellipsis a, td a[href*='/board/view']")
            if not a:
                continue
            lid = parse_qs(urlparse(a["href"]).query).get("linkId", [""])[0]
            if not lid or lid in seen:
                continue
            seen.add(lid)
            posted = next((norm_date(td.get_text()) for td in tr.find_all("td") if norm_date(td.get_text())), "")
            out.append((lid, clean(a.get("title") or a.get_text()), posted,
                        f"{self.BASE}/board/view?linkId={lid}&menuId=MENU01108"))
        return out

    def body(self, sp):
        v = sp.select_one("div.viewContent")
        return clean(v.get_text(" ")) if v else ""


class NECA(Board):
    NAME, AGENCY, MINISTRY = "NECA", "한국보건의료연구원", "보건복지부"
    BASE = "https://www.neca.re.kr"
    LISTS = [(BASE + "/lay1/bbs/S1T12C49/A/12/list.do", {}),   # 공지사항(연구과제·공모)
             (BASE + "/lay1/bbs/S1T12C81/A/29/list.do", {})]   # 입찰공고(연구용역)
    PAGES = 1

    def page_param(self, p):
        return {"cpage": p}

    def rows(self, sp, list_url):
        out = []
        for tr in sp.select("table tbody tr"):
            a = tr.select_one("td.title a")
            if not a:
                continue
            sid = parse_qs(urlparse(a["href"]).query).get("article_seq", [""])[0]
            d = tr.select_one("td.date")
            out.append((sid, clean(a.get_text()), norm_date(d.get_text()) if d else "", urljoin(list_url, a["href"])))
        return out

    def body(self, sp):
        v = sp.select_one("table.view_style_1")
        return clean(v.get_text(" ")) if v else ""


class KEITI(Board):
    NAME, AGENCY, MINISTRY = "환경부(KEITI)", "한국환경산업기술원", "환경부"
    BASE = "https://www.keiti.re.kr"
    LISTS = [(BASE + "/site/keiti/ex/board/List.do", {"cbIdx": 277, "searchExt1": "24000400"})]  # R&D 분류

    def rows(self, sp, list_url):
        out = []
        for a in sp.select("ul.list li a[href*='View.do']"):
            sid = parse_qs(urlparse(a["href"]).query).get("bcIdx", [""])[0]
            subj, d = a.select_one(".subject"), a.select_one(".date")
            out.append((sid, clean(subj.get_text() if subj else a.get_text()),
                        norm_date(d.get_text()) if d else "", urljoin(self.BASE, a["href"])))
        return out

    def body(self, sp):
        v = sp.select_one("dl.view .content") or sp.select_one("dl.view")
        return clean(v.get_text(" ")) if v else ""
