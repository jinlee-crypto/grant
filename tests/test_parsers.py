"""실제 사이트에서 확인한 HTML 구조(2026-09-15)로 만든 파서 테스트. 사이트 개편 시 여기부터 깨집니다."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sources import iris, htdream, nrf
from sources.board import KHIDI, NECA, KEITI
from sources.base import extract_period, soup

FX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fixtures")
rd = lambda n: open(os.path.join(FX, n), encoding="utf-8").read()


def test_iris():
    items, pages = iris.parse_list(rd("list.html"), "ancmIng")
    assert pages == 3 and items[0]["src_id"] == "024077" and items[0]["ministry"] == "보건복지부"
    d = iris.parse_detail(rd("detail.html"))
    assert d["rcv_end"] == "2026-10-14"


def test_htdream():
    html = """<table><tbody><tr><td>2026</td><td></td><td class="text-left">
    <a href="#" onclick="fn_select2('8886', 'Y')"><span class="list-title">브릿지 연수 2차 공고&nbsp;안내</span></a></td>
    <td> 2026-09-10 ~ 2026-09-30 </td><td>~</td><td>48</td></tr></tbody></table>"""
    it = htdream.parse_list(html)[0]
    assert it["src_id"] == "8886" and it["rcv_end"] == "2026-09-30"
    det = """<table class="board"><tbody><tr><th>공고번호</th><td>X</td><th>공고시작일</th><td>2026-09-10</td></tr>
    <tr><th>공고종료일</th><td>2026-09-30</td></tr><tr><td colspan=4><div class="se-contents">본문</div></td></tr></tbody></table>"""
    assert htdream.parse_detail(det)["rcv_end"] == "2026-09-30"


def test_nrf():
    html = """<div class="nums-total">7</div><div class="public-notice-block"><div class="pnb-state">
    <div class="state-block"><span class="block-text">접수대기</span></div><div class="state-block cfy--date"><span class="block-text">D-29</span></div></div>
    <div class="pnb-title"><span class="title-category">신규과제공모</span>
    <a href="javascript:;" class="title-name view_btn" data-post_no="282050" data-post_close_yn="N" data-biz_no="10">AI 기반 대학 혁신사업 신규과제 공모</a></div>
    <div class="pnb-bread-crumb"><span class="bread-crumb-text">[기초연구사업 &gt; 기반구축]</span></div>
    <div>접수일자 : 2026-10-01 09:00 ~ 2026-10-14 18:00</div></div>"""
    items, pages = nrf.parse_list(html)
    it = items[0]
    assert pages == 7 and it["status"] == "접수대기" and it["rcv_end"] == "2026-10-14" and "기초연구사업" in it["program"]
    d = nrf.parse_detail("<div class='cms-contents'>등록일 : 2026-09-14 14:01 공고내용 <주무부처> 부총리 겸 과학기술정보통신부 장관</div>")
    assert d["posted"] == "2026-09-14" and d["ministry"] == "과학기술정보통신부"


def test_khidi():
    html = """<table class="tstyle_list"><tbody><tr><td class="num">978</td><td class="ellipsis">
    <a href="/board/view?pageNum=1&amp;no1=978&amp;linkId=48949906&amp;menuId=MENU01108" title="규제 대응 3차 공고(9월 28일(월) 18시까지)">규제</a></td>
    <td>관리자</td><td>2026-09-11</td><td>736</td></tr></tbody></table>"""
    rows = KHIDI().rows(soup(html), "")
    assert rows[0][0] == "48949906" and rows[0][2] == "2026-09-11"
    assert extract_period(rows[0][1], rows[0][2]) == ("", "2026-09-28")
    assert "공고" in KHIDI().body(soup("<h1></h1><table class='tstyle_view'></table><div class='viewContent'>진흥원 공고 제2026-275호</div>"))


def test_neca():
    html = """<table class="list_style_1"><tbody><tr><td>652</td><td class="title">
    <a href="view.do?article_seq=17600&amp;cpage=">길라잡이 서비스 모집 공고</a></td><td>팀</td><td class="date">2026.08.26</td></tr></tbody></table>"""
    r = NECA().rows(soup(html), "https://www.neca.re.kr/lay1/bbs/S1T12C49/A/12/list.do")[0]
    assert r[0] == "17600" and r[2] == "2026-08-26" and r[3].endswith("/A/12/view.do?article_seq=17600&cpage=")


def test_keiti():
    html = """<ul class="list col5"><li><div class="cate"><a href="/site/keiti/ex/board/View.do?cbIdx=277&amp;bcIdx=40291">
    <span class="cateName">R&amp;D</span><span class="date">2026-05-15</span><span class="subject">기술수요조사</span></a></div></li></ul>"""
    r = KEITI().rows(soup(html), "")[0]
    assert r[0] == "40291" and r[3].startswith("https://www.keiti.re.kr/site/keiti/ex/board/View.do")


def test_extract_period():
    assert extract_period("접수기간 : 2026. 9. 1.(월) ~ 2026. 9. 30.(화) 18:00") == ("2026-09-01", "2026-09-30")
    assert extract_period("신청기간: 2026년 10월 1일 ~ 10월 14일") == ("2026-10-01", "2026-10-14")
    assert extract_period("제출기한 : 2026.11.03 17:00까지")[1] == "2026-11-03"
    assert extract_period("아무 날짜도 없음") == ("", "")


def test_title_short_deadlines():
    assert extract_period("참여기관 모집 공고(~8.2", "2026-07-20")[1] == "2026-08-02"
    assert extract_period("사절단 참여기업 모집 안내(~7.31.)", "2026-07-01")[1] == "2026-07-31"
    assert extract_period("참가 지원 사업 공고 (기한연장, ~8/6(목) 16:00", "2026-07-25")[1] == "2026-08-06"
    assert extract_period("모집 (~1.10.)", "2026-12-20")[1] == "2027-01-10"
