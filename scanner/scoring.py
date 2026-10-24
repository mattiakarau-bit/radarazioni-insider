"""Two independent rule scores. Neither score is a validated BUY signal."""
from __future__ import annotations


def screen(item: dict, fin: dict | None, insider_count: int = 1) -> dict:
    fin = fin or {}
    amount = item.get('amount', 0)
    strength = 50 if amount >= 500_000 else 35 if amount >= 100_000 else 20 if amount >= 25_000 else 8 if amount >= 5_000 else 0
    insider_reasons = [f'Importo dichiarato: {amount:,.2f} USD']
    title = item.get('officer_title', '').upper()
    if any(t in title for t in ('CEO', 'CHIEF EXECUTIVE', 'CFO', 'CHIEF FINANCIAL')):
        strength += 30
        insider_reasons.append('Ruolo dichiarato CEO/CFO')
    elif item.get('officer') or item.get('director'):
        strength += 20
        insider_reasons.append('Ruolo dichiarato dirigente/amministratore')
    # Names, joint owners and legal entities are not evidence of independent decisions.
    # Reserve the remaining 20 points until affiliations can be verified from sources.
    warnings = ['Indipendenza e collegamenti tra dichiaranti non verificati: nessun bonus cluster',
                'La forza misura importo e ruolo, non il rendimento atteso',
                'Valutazione e prezzo corrente non verificati: opportunità limitata a 49/100',
                'Modello ML NON addestrato/validato; nessuna notifica BUY']
    opportunity = 0
    reasons = []
    for key, name, weight in [('revenue_growing', 'Fatturato annuale in crescita', 25),
                              ('eps_growing', 'EPS annuale in crescita', 25),
                              ('cashflow_positive', 'Cassa operativa positiva per tre esercizi consecutivi', 20)]:
        if fin.get(key) is True:
            opportunity += weight
            reasons.append(name)
        else:
            warnings.append(name + (': dati insufficienti' if fin.get(key) is None else ': requisito non soddisfatto'))
    # No verified valuation provider exists yet. Do not accept caller-supplied flags
    # or treat cashflow positivity as evidence of cheapness or adequate free cashflow.
    opportunity = min(opportunity, 49)
    if fin.get('cashflow_positive') is not True:
        opportunity = min(opportunity, 39)
        warnings.append('Flussi di cassa insufficienti/non verificati: opportunità limitata a 39/100')
    return {'insider_strength_score': strength, 'opportunity_score': opportunity,
            'score': opportunity,  # Compatibility for old clients: never expose strength as opportunity.
            'insider_reasons': insider_reasons, 'reasons': reasons, 'warnings': warnings,
            'independence_verified': False, 'verified_independent_insiders': None,
            'valuation_verified': False,
            'financial_data_complete': all(fin.get(k) is not None for k in ('revenue_growing', 'eps_growing', 'cashflow_positive')),
            'priority': 'Opportunità non verificata', 'notify': False, 'buy_signal': False,
            'model': 'Due punteggi a regole v3 (NON machine learning)'}
