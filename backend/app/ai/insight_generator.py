"""
AI Insight Generator — standalone module.

Synthesizes actionable insights from forecast, risk, anomaly, and stock data.
Produces categorized messages (critical / warning / info) for the AI dashboard.
"""



def generate_insights(
    forecasts=None,
    zone_risks=None,
    anomalies=None,
    stock_levels=None,
):
    """
    Auto-generate actionable insights from AI module outputs.

    Parameters
    ----------
    forecasts : list[dict]  — from forecast_engine.predict_depletion()
    zone_risks : list[dict] — from risk_predictor.predict_zone_risks()['zone_risks']
    anomalies : list[dict]  — from anomaly_detector.detect_anomalies()['anomalies']
    stock_levels : list[dict] — raw stock rows with 'resource_type' and 'quantity'

    Returns
    -------
    dict with 'insights' list, 'summary', 'explanation'
    """
    insights = []
    forecasts = forecasts or []
    zone_risks = zone_risks or []
    anomalies = anomalies or []
    stock_levels = stock_levels or []

    # ── Forecast-based insights ──
    # `days_until_depletion` is "Stable" for resources with no measurable burn
    # rate, so it must be coerced before comparison — the previous direct
    # comparison raised TypeError as soon as one stable resource appeared.
    def _days(forecast, default=999.0):
        value = forecast.get('days_until_depletion', default)
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    urgent = [f for f in forecasts if _days(f) <= 7]
    warning = [f for f in forecasts if 7 < _days(f) <= 14]

    if urgent:
        names = ', '.join(set(f.get('resource', '?') for f in urgent))
        insights.append({
            'severity': 'critical',
            'category': 'forecast',
            'message': f'⚠️ CRITICAL: {len(urgent)} resource(s) will deplete within 7 days — {names}.',
            'explanation': f'Linear regression forecasts predict imminent depletion for {names}. Immediate restocking required.',
        })
    if warning:
        names = ', '.join(set(f.get('resource', '?') for f in warning))
        insights.append({
            'severity': 'warning',
            'category': 'forecast',
            'message': f'⏳ WARNING: {len(warning)} resource(s) depleting within 14 days — {names}.',
            'explanation': f'Depletion forecast models show {names} trending toward shortage within two weeks.',
        })

    # ── Risk-based insights ──
    critical_zones = [z for z in zone_risks if z.get('risk_level') == 'Critical']
    high_zones = [z for z in zone_risks if z.get('risk_level') == 'High']

    if critical_zones:
        znames = ', '.join(z.get('zone_name', '?') for z in critical_zones)
        insights.append({
            'severity': 'critical',
            'category': 'risk',
            'message': f'🔴 CRITICAL RISK: {len(critical_zones)} zone(s) at critical risk level — {znames}.',
            'explanation': f'Weighted risk model indicates critical status for {znames}. Contributing factors include high pending requests, severe demand, and stock shortages.',
        })
    if high_zones:
        znames = ', '.join(z.get('zone_name', '?') for z in high_zones)
        insights.append({
            'severity': 'warning',
            'category': 'risk',
            'message': f'🟠 HIGH RISK: {len(high_zones)} zone(s) at elevated risk — {znames}.',
            'explanation': f'Risk prediction model flags {znames} as high risk. Proactive resource allocation advised.',
        })

    # ── Anomaly-based insights ──
    high_anomalies = [a for a in anomalies if a.get('severity') == 'high']
    if high_anomalies:
        types = ', '.join(set(a.get('type', 'unknown') for a in high_anomalies))
        insights.append({
            'severity': 'critical',
            'category': 'anomaly',
            'message': f'🚨 ANOMALY: {len(high_anomalies)} high-severity anomalies detected — types: {types}.',
            'explanation': 'IsolationForest and threshold-based detectors identified unusual patterns requiring investigation.',
        })
    med_anomalies = [a for a in anomalies if a.get('severity') == 'medium']
    if med_anomalies:
        insights.append({
            'severity': 'warning',
            'category': 'anomaly',
            'message': f'⚡ {len(med_anomalies)} medium-severity anomalies detected. Review recommended.',
            'explanation': 'Anomaly detection models flagged patterns outside normal operating thresholds.',
        })

    # ── Stock-based insights ──
    if stock_levels:
        low_stock = [s for s in stock_levels if (s.get('quantity') or 0) < 100]
        if low_stock:
            resources = ', '.join(set(s.get('resource_type', '?') for s in low_stock))
            insights.append({
                'severity': 'warning',
                'category': 'stock',
                'message': f'📦 Low stock alert: {len(low_stock)} entries below 100 units — {resources}.',
                'explanation': 'Current stock levels for these resources are critically low. Replenishment needed.',
            })

    # ── No issues ──
    if not insights:
        insights.append({
            'severity': 'info',
            'category': 'info',
            'message': 'All systems operating within normal parameters. No critical issues detected.',
            'explanation': 'No forecast, risk, anomaly, or stock alerts triggered.',
        })

    # Build summary
    n_critical = sum(1 for i in insights if i['severity'] == 'critical')
    n_warning = sum(1 for i in insights if i['severity'] == 'warning')

    return {
        'insights': insights,
        'summary': f'{len(insights)} insights generated ({n_critical} critical, {n_warning} warnings).',
        'explanation': (
            'Insights auto-generated from AI module outputs: forecast depletion predictions, '
            'zone risk assessments, anomaly detection alerts, and stock level monitoring. '
            'Uses rule-based summarization combined with model predictions.'
        ),
    }
