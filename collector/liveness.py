"""Dead-domain maintenance for curated-list entries.

Curated lists (UT1 and others) rarely remove anything, so a large share of
their entries are domains that no longer exist. Each one still costs an entry
on every FortiGate. This module checks list entries in the DNS on a rolling
schedule and keeps out of the feed the ones whose name no longer exists.

Safety rules:
- Only NXDOMAIN ("this name does not exist", from the DNS itself) counts as
  dead. Timeouts, server failures and names that exist without an address are
  never treated as dead.
- A name is only dropped after several NXDOMAIN answers spread over at least
  a couple of weeks, confirmed by two independent resolvers each time.
- Dropped names keep being re-checked; one that comes back returns to the feed
  on the next run.
- Only list entries are pruned. Sites the collector confirmed itself (which
  have their own 60-day liveness rule) and reviewer confirmations
  (seeds/confirmed.txt) are never touched.
"""
from __future__ import annotations

import concurrent.futures as cf
import datetime as dt
import random
import socket
import struct

NOERROR, SERVFAIL, NXDOMAIN = 0, 2, 3


def _query(name: str, server: str, timeout: float) -> int | None:
    """DNS RCODE for an A query of `name`, or None if no answer."""
    try:
        labels = [p.encode("idna") for p in name.rstrip(".").split(".")]
    except UnicodeError:
        return None
    if any(not 0 < len(p) < 64 for p in labels):
        return None
    tid = random.randint(0, 0xFFFF)
    pkt = (struct.pack(">HHHHHH", tid, 0x0100, 1, 0, 0, 0)
           + b"".join(bytes([len(p)]) + p for p in labels) + b"\x00"
           + struct.pack(">HH", 1, 1))
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    try:
        for _ in range(2):  # one retry on timeout
            try:
                s.sendto(pkt, (server, 53))
                data, _ = s.recvfrom(4096)
            except socket.timeout:
                continue
            if len(data) >= 4 and struct.unpack(">H", data[:2])[0] == tid:
                return data[3] & 0x0F
        return None
    except OSError:
        return None
    finally:
        s.close()


def rcode(name: str, servers: list[str], timeout: float = 3.0) -> int | None:
    """NXDOMAIN only if every resolver agrees; otherwise the first answer."""
    first = _query(name, servers[0], timeout)
    if first != NXDOMAIN:
        return first
    for srv in servers[1:]:
        if _query(name, srv, timeout) != NXDOMAIN:
            return None  # resolvers disagree: inconclusive
    return NXDOMAIN


def maintain(state: dict, names: set[str], cfg: dict, today: dt.date, metrics, log) -> set[str]:
    """Check a budget of list names; return the names to keep out of the feed."""
    reg = state.setdefault("liveness", {})
    servers = cfg.get("resolvers", ["1.1.1.1", "8.8.8.8"])
    budget = cfg.get("budget", 6000)
    alive_days = cfg.get("recheck_alive_days", 14)
    dead_days = cfg.get("recheck_dead_days", 3)
    need_checks = cfg.get("drop_after_checks", 3)
    need_days = cfg.get("drop_after_days", 14)
    t = today.isoformat()

    def age(s):
        return (today - dt.date.fromisoformat(s)).days if s else 10 ** 6

    # Forget names that are no longer on any list.
    for n in [n for n in reg if n not in names]:
        del reg[n]

    # Network sanity probe: if the resolvers can't be reached, or don't
    # return NXDOMAIN for a name that can't exist, skip this run entirely.
    probe_nx = rcode(f"nx-{random.randint(10**8, 10**9)}.invalid-probe.example", servers)
    probe_ok = rcode("example.com", servers)
    if probe_ok != NOERROR or probe_nx != NXDOMAIN:
        metrics["liveness_skipped"] += 1
        log(f"[liveness] DNS probe failed (ok={probe_ok}, nx={probe_nx}); skipped this run")
    else:
        def due(n):
            r = reg.get(n)
            if not r:
                return True
            return age(r["checked"]) >= (dead_days if r.get("nx") else alive_days)
        todo = [n for n in names if due(n)]
        todo.sort(key=lambda n: (n in reg, reg.get(n, {}).get("checked", "")))
        todo = todo[:budget]
        with cf.ThreadPoolExecutor(cfg.get("workers", 48)) as ex:
            for n, rc in zip(todo, ex.map(lambda n: rcode(n, servers), todo)):
                metrics["liveness_checked"] += 1
                if rc is None or rc == SERVFAIL:
                    metrics["liveness_inconclusive"] += 1
                    continue  # unknown: don't update, try again next time
                r = reg.setdefault(n, {})
                r["checked"] = t
                if rc == NXDOMAIN:
                    metrics["liveness_nxdomain"] += 1
                    r["nx"] = r.get("nx", 0) + 1
                    r.setdefault("first_nx", t)
                else:
                    if r.get("nx", 0) >= need_checks and age(r.get("first_nx")) >= need_days:
                        metrics["liveness_revived"] += 1
                    r.pop("nx", None)
                    r.pop("first_nx", None)

    dead = {n for n, r in reg.items()
            if r.get("nx", 0) >= need_checks and age(r.get("first_nx")) >= need_days}
    metrics["liveness_pruned"] = len(dead)
    metrics["liveness_tracked"] = len(reg)
    metrics["liveness_watching"] = sum(1 for r in reg.values() if r.get("nx")) - len(dead)
    log(f"[liveness] {metrics['liveness_checked']} checked, {len(dead)} dead list "
        f"entries kept out of the feed, {metrics['liveness_watching']} failing but not yet dropped")
    return dead
