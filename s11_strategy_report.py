"""Independent S11 report: fresh 1T data, protected stars, dedicated email."""

import argparse
from email.message import EmailMessage
import os

from daily_predictions_fast import generate_fast_report_data
from features.fast_notifier import deliver_report_message
from features.ligainsider_signals import enrich_reports_with_ligainsider_signals
from features.lineup_optimizer import build_lineup_payload
from features.strategy_report import build_strategy_report, strategy_html, write_strategy_report


def send_strategy_mail(report, path):
    address, password = os.getenv('EMAIL_USER'), os.getenv('EMAIL_PASS')
    if not address or not password:
        print('S11 email skipped: EMAIL_USER/EMAIL_PASS missing. Report files are available.')
        return False
    message = EmailMessage()
    message['Subject'] = 'Kickbase S11-Strategie – eigenständiger Report'
    message['From'] = address
    message['To'] = address
    message.set_content(
        'Dein eigenständiger S11-Report ist als HTML-Mail und im Anhang verfügbar. '
        'Eigene Spieler mit aktuellem Marktwert über 25 Mio. Euro sind vor Verkauf geschützt. '
        'Es wurden keine Transfers ausgeführt.'
    )
    message.add_alternative('<html><body>' + strategy_html(report) + '</body></html>', subtype='html')
    message.add_attachment(path.read_bytes(), maintype='text', subtype='html', filename=path.name)
    deliver_report_message(message)
    print('S11 strategy email sent.')
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--no-email', action='store_true', help='Generate files without sending an email.')
    args = parser.parse_args(argv)
    data = generate_fast_report_data(source='S11 Strategy')
    market, squad = enrich_reports_with_ligainsider_signals(data['market_df'], data['squad_df'])
    payload = build_lineup_payload(
        data['token'], data['league_id'], data['user_id'], squad, data['predictions_df'],
        history_df=data['history_df'], forecast_snapshot=data['forecast_snapshot'], market_df=market,
    )
    report = build_strategy_report(payload)
    path = write_strategy_report(report)
    if not args.no_email:
        send_strategy_mail(report, path)
    return report


if __name__ == '__main__':
    main()
