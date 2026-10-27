"""Coverage of verified market gates, not counts of tickers in old SEC history."""
from scanner.market_math import number


def coverage(companies,details,radar,ml):
    candidates=[c for c in companies if c['selection_status'] in ('pending','selected')]
    def windows(c):return details[c['cik']].get('significant_windows',[])
    counts=dict(candidates=len(candidates),
        historical_market_prices_verified=sum(any(w.get('historical_price_verified') is True for w in windows(c)) for c in candidates),
        current_prices_verified=sum(c.get('current_checks',{}).get('current_price_verified') is True for c in candidates),
        historical_capitalizations_verified=sum(any(number(w.get('historical_market_cap')) and w['historical_market_cap']>0 for w in windows(c)) for c in candidates),
        current_capitalizations_verified=sum(c.get('market_cap_verified') is True for c in candidates),
        within_15_pct_verified=sum(any(w.get('split_comparison_verified') is True and number(w.get('distance_from_insider_pct')) and abs(w['distance_from_insider_pct'])<=15 for w in windows(c)) for c in candidates),
        complete_current_financial_checks=radar['stats']['companies_current_financials_verified'],
        selected=len(radar['groups']),preliminary=len(candidates)-len(radar['groups']))
    return dict(version=1,as_of=radar['as_of'],counts=counts,financial_progress=radar.get('financial_progress',{}),
                active_public_price_provider=None,personal_adapter='Tiingo own-token/internal use; not authenticated or activated for this public pipeline',
                proximity_default_pct=15,ml=dict(trained=bool(ml.get('trained')),verified_targets=ml.get('verified_targets'),
                                               metrics=ml.get('metrics'),status=ml.get('status'),
                                               significant_rise_hypothesis='At least 20 percentage points above benchmark in 180 days; untested, not deployed'),
                buy_signal=False,notify=False)
