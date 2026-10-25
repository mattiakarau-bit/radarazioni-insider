"""Durable accession queue, fair scheduling and auditable per-index counts."""
from datetime import date, timedelta
from scanner.identity import filing_key


def merge_pending(pending, entries, seen):
    out = {filing_key(x['url']): dict(x) for x in pending if filing_key(x['url']) not in seen}
    for x in entries:
        key = filing_key(x['url'])
        if key not in seen and key not in out:
            out[key] = dict(x, attempts=0)
    return list(out.values())


def select_queue(pending, limit, today):
    eligible = [x for x in pending if x.get('retry_after', '') <= today]
    recent = sorted(eligible, key=lambda x: (x['filed'], x['url']), reverse=True)
    # Reserve a third for the oldest eligible filings. Small limits alternate by day.
    old_slots = max(1, limit // 3) if limit > 1 else int(date.fromisoformat(today).toordinal() % 2 == 0)
    chosen = recent[:limit-old_slots]
    keys = {filing_key(x['url']) for x in chosen}
    oldest = sorted(eligible, key=lambda x: (x['filed'], x['url']))
    chosen += [x for x in oldest if filing_key(x['url']) not in keys][:limit-len(chosen)]
    return chosen


def record_failure(filing, today, error):
    filing['attempts'] = filing.get('attempts', 0) + 1
    filing['last_error'] = error[:200]
    filing['retry_after'] = (date.fromisoformat(today) + timedelta(days=min(7, 2 ** min(filing['attempts']-1, 3)))).isoformat()


def coverage_report(indexes, seen, pending, checked, success, failed):
    by_day = []
    for day, record in sorted(indexes.items(), reverse=True):
        keys = set(record['accessions'])
        done = len(keys & seen)
        by_day.append(dict(day=day, indexed=len(keys), processed=done, pending=len(keys)-done,
                           index_url=record['url'], checked_utc=record['checked_utc']))
    total = sum(x['indexed'] for x in by_day)
    done = sum(x['processed'] for x in by_day)
    return dict(days_checked=checked, form4_listed_in_checked_days=sum(x['indexed'] for x in by_day if x['day'] in checked),
                new_forms_this_run=success, failed_forms_this_run=failed,
                unprocessed_listed_forms=len(pending), known_indexed_forms=total,
                known_processed_forms=done, known_completion_pct=round(100*done/total, 2) if total else None,
                oldest_pending_date=min((x['filed'] for x in pending), default=None),
                retry_pending_forms=sum(x.get('attempts', 0)>0 for x in pending), by_day=by_day,
                note='Copertura dei soli indici registrati; non totale SEC. Form 4/A conservati in revisione, esclusi dai segnali; latenza degli indici notturni.')
