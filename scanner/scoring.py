"""Conservative, auditable SCREENING score (not a BUY decision or ML)."""
from __future__ import annotations


def screen(item: dict, fin: dict | None, insider_count: int = 1) -> dict:
    score, reasons, warnings = 0, [], []
    amount = item['amount']
    if amount >= 500_000:
        score += 25; reasons.append('Acquisto di almeno 500.000 USD')
    elif amount >= 100_000:
        score += 18; reasons.append('Acquisto di almeno 100.000 USD')
    elif amount >= 25_000:
        score += 10; reasons.append('Acquisto di almeno 25.000 USD')
    elif amount >= 5_000:
        score += 4
    title = item.get('officer_title', '').upper()
    if any(t in title for t in ('CEO', 'CHIEF EXECUTIVE', 'CFO', 'CHIEF FINANCIAL')):
        score += 15; reasons.append('Acquisto di CEO/CFO')
    elif item.get('officer') or item.get('director'):
        score += 10; reasons.append('Acquisto di dirigente o amministratore')
    if insider_count >= 2:
        score += 10; reasons.append('Più insider distinti nello stesso intervallo di 14 giorni')
    if fin:
        if fin.get('revenue_growing') is True:
            score += 20; reasons.append('Fatturato annuale in crescita nel periodo verificabile')
        if fin.get('eps_growing') is True:
            score += 20; reasons.append('Utili per azione in crescita nel periodo verificabile')
        if fin.get('cashflow_positive') is True:
            score += 10; reasons.append('Flussi di cassa operativi positivi in tre esercizi')
        for key, name in [('revenue_growing', 'Fatturato'), ('eps_growing', 'Utili per azione'), ('cashflow_positive', 'Flusso di cassa')]:
            if fin.get(key) is None:
                warnings.append(f'{name}: dati annuali insufficienti')
            elif fin.get(key) is False:
                warnings.append(f'{name}: requisito non soddisfatto')
    else:
        warnings.append('Dati finanziari non disponibili')
    warnings.extend(['Prezzo corrente, ribasso dai massimi e valutazione NON verificati',
                     'Modello ML NON ancora addestrato e validato'])
    ready = bool(fin and fin.get('revenue_growing') is True and
                 fin.get('eps_growing') is True and fin.get('cashflow_positive') is True and
                 score >= 70 and amount >= 25_000)
    return {'score': min(score, 100), 'priority': 'Da approfondire' if ready else 'Osservazione',
            'notify': ready, 'reasons': reasons, 'warnings': warnings,
            'model': 'Regole trasparenti v1 (NON machine learning)',
            'buy_signal': False}
