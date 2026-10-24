"""Stable SEC identities: the same accession can appear under several owner CIKs."""
import re
from datetime import date


def iso_date(value):
    value = str(value or "").strip()
    if re.fullmatch(r"\d{8}", value):
        value = f"{value[:4]}-{value[4:6]}-{value[6:]}"
    return date.fromisoformat(value).isoformat()


def filing_key(url):
    match = re.search(r"(\d{10})-?(\d{2})-?(\d{6})(?:[./#]|$)", url)
    return "-".join(match.groups()) if match else url


def event_key(event):
    return filing_key(event['form_url']) + '#' + event['id'].rsplit('#', 1)[-1]


def normalize_events(events):
    merged = {}
    for event in events:
        event = dict(event)
        event['filed'] = iso_date(event['filed'])
        event['transaction_date'] = iso_date(event['transaction_date'])
        event['id'] = event_key(event)
        merged[event['id']] = event
    return list(merged.values())
