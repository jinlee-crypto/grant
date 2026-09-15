"""공고 수집기. 사용: python collector.py [--only IRIS NECA ...]"""
import argparse
import sys
from datetime import datetime

from sources import SOURCES
from sources.base import Fetcher
from store import Store


def collect(store=None, only=None, log=print):
    st = store or Store()
    summary = {}
    for name, fn in SOURCES:
        if only and name not in only:
            continue
        n_new = n_upd = 0
        log(f"[{name}]")
        try:
            for it in fn(Fetcher(), lambda sid, _n=name: st.known(f"{_n}:{sid}"), log=log):
                it["source"], it["ancm_id"] = name, f"{name}:{it['src_id']}"
                if st.upsert(it):
                    n_new += 1
                else:
                    n_upd += 1
            summary[name] = (n_new, n_upd, "")
        except Exception as e:  # 한 출처가 실패해도 나머지는 계속
            log(f"  !! {name} 실패: {e}")
            summary[name] = (n_new, n_upd, str(e)[:200])
        st.log_run(name, *summary[name])
    st.save_collected()
    log("완료 " + datetime.now().strftime("%Y-%m-%d %H:%M"))
    for k, (a, b, e) in summary.items():
        log(f"  {k}: 신규 {a} · 갱신 {b}" + (f" · 오류 {e}" if e else ""))
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="특정 출처만 (예: IRIS NECA)")
    s = collect(only=ap.parse_args().only)
    sys.exit(1 if s and all(e for *_, e in s.values()) else 0)
