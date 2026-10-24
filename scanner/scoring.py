"""Evidence-gated Radar Score. Missing data is not negative financial evidence."""
from dataclasses import dataclass
from datetime import date
from math import isfinite


@dataclass(frozen=True)
class ValuationEvidence:
    """Internal adapter contract, not an HTTP/client flag. No production provider connected.

    A future licensed adapter must reconcile price, shares/classes, currency, date and
    multiples before constructing this record. Fixture tests do not approve a provider.
    """
    as_of: str
    source_url: str
    market_cap: float
    currency: str
    favorable: bool
    review_reference: str


def valuation_valid(evidence, as_of):
    if not isinstance(evidence, ValuationEvidence):
        return False
    try:
        age = (date.fromisoformat(as_of)-date.fromisoformat(evidence.as_of)).days
    except (TypeError,ValueError):
        return False
    return (0 <= age <= 7 and evidence.source_url.startswith('https://') and
            bool(evidence.review_reference) and evidence.currency=='USD' and
            isfinite(evidence.market_cap) and evidence.market_cap>0)


def screen(item, fin, insider_count=1, *, valuation=None):
    fin = fin or {}
    amount = item.get('amount',0)
    strength = 50 if amount>=500000 else 35 if amount>=100000 else 20 if amount>=25000 else 8 if amount>=5000 else 0
    insider_reasons = [f'Importo dichiarato: {amount:,.2f} USD']
    title = item.get('officer_title','').upper()
    if any(t in title for t in ('CEO','CHIEF EXECUTIVE','CFO','CHIEF FINANCIAL')):
        strength += 30; insider_reasons.append('Ruolo CEO/CFO dichiarato')
    elif item.get('officer') or item.get('director'):
        strength += 20; insider_reasons.append('Ruolo dirigente/amministratore dichiarato')
    warnings = ['Indipendenza dei dichiaranti non verificata: nessun bonus cluster',
                'Pesi e soglie a regole, non probabilità di rendimento; nessun BUY o notifica']
    warnings.extend(fin.get('data_warnings',[]))
    opportunity, reasons = 0, []
    for key,label,weight in [('revenue_growing','Ricavi totali annuali in crescita',25),
                             ('eps_growing','EPS annuali in crescita e positivi',25),
                             ('cashflow_positive','Cassa operativa positiva in tre esercizi',20)]:
        value = fin.get(key)
        if key=='eps_growing' and fin.get('eps_latest_positive') is not True:
            value = None if fin.get('eps_latest_positive') is None else False
        if value is True:
            opportunity += weight; reasons.append(label)
        elif value is None:
            warnings.append(label+': dato non verificabile/insufficiente')
        else:
            warnings.append(label+': criterio non soddisfatto (non equivale da solo a dissesto)')
    complete = all(fin.get(k) is not None for k in ('revenue_growing','eps_growing','cashflow_positive','eps_latest_positive','cashflow_latest_positive'))
    fundamentals_verified = bool(fin.get('evidence_valid') is True and complete and fin.get('fresh') is True)
    valid_valuation = valuation_valid(valuation,item.get('analysis_as_of',item.get('filed')))
    if valid_valuation and valuation.favorable:
        opportunity += 30; reasons.append('Valutazione favorevole con evidenza riconciliata')
    raw = round(0.7*opportunity+0.3*strength,1)
    provisional, caps = raw, []
    if not valid_valuation:
        provisional=min(provisional,49); caps.append('Valutazione assente/non verificata: massimo provvisorio 49')
    if not fundamentals_verified:
        provisional=min(provisional,29); caps.append('Fondamentali incompleti, obsoleti o perimetro non verificato: massimo provvisorio 29')
    if fin.get('cashflow_positive') is not True:
        provisional=min(provisional,39); caps.append('Storico cassa triennale non soddisfatto/verificato: massimo 39')
    # Only actual current losses/negative cash, not failure of a monotonic growth test.
    financial_problem = fin.get('eps_latest_positive') is False or fin.get('cashflow_latest_positive') is False
    if financial_problem:
        provisional=min(provisional,29); caps.append('Ultimo EPS o flusso di cassa negativo: massimo 29')
    status = 'verificato' if fundamentals_verified and valid_valuation else 'provvisorio' if fundamentals_verified else 'non_verificabile'
    radar = provisional if status!='non_verificabile' else None
    quality_pass = bool(status=='verificato' and valuation.favorable and not financial_problem and
                        all(fin.get(k) is True for k in ('revenue_growing','eps_growing','cashflow_positive','eps_latest_positive')))
    return dict(radar_score=radar,radar_provisional=provisional,radar_uncapped=raw,radar_caps=caps,
                radar_weights=dict(opportunity=0.7,insider=0.3),score_status=status,
                insider_strength_score=strength,opportunity_score=opportunity,score=provisional,
                insider_reasons=insider_reasons,reasons=reasons,warnings=warnings,
                independence_verified=False,verified_independent_insiders=None,
                valuation_verified=valid_valuation,fundamentals_verified=fundamentals_verified,
                financial_data_complete=complete,financial_problem=financial_problem,quality_pass=quality_pass,
                priority={'verificato':'Screening verificato','provvisorio':'Provvisorio','non_verificabile':'Non verificabile'}[status],
                notify=False,buy_signal=False,model='Radar Score v0.6.0 — regole non validate storicamente')
