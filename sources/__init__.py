from . import iris, htdream, nrf
from .board import KHIDI, NECA, KEITI

# (출처 이름, collect 함수). 순서 = 중복 공고일 때 대표로 보여줄 우선순위
SOURCES = [
    ("IRIS", iris.collect),
    ("한국연구재단", nrf.collect),
    ("HT Dream", htdream.collect),
    ("KHIDI", KHIDI().collect),
    ("NECA", NECA().collect),
    ("환경부(KEITI)", KEITI().collect),
]
