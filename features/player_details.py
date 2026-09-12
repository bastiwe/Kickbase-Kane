"""Player detail fields from observed Kickbase v4 profile and performance data."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from features.lineup_optimizer import number


def build_details(profile, performance, table, now=None):
    now = now or datetime.now(timezone.utc)
    teams = {str(t['tid']): t for t in table.get('it', [])}
    games = {}
    for season in performance.get('it', []):
        if season.get('n') != 'Bundesliga':
            continue
        for match in season.get('ph', []):
            try:
                stamp = datetime.fromisoformat(match['md'].replace('Z', '+00:00'))
            except (ValueError, KeyError, TypeError):
                continue
            if stamp.tzinfo is None:
                continue
            games[str(match.get('mi') or match['md'])] = (stamp, match)
    ordered = sorted(games.values(), key=lambda pair: pair[0])
    completed = [(d, m) for d, m in ordered if d <= now and m.get('mdst') == 2
                 and number(m.get('p')) is not None]

    def opponent(match, team):
        home, away = str(match.get('t1')), str(match.get('t2'))
        if team not in (home, away):
            return {'opponent': 'Unbekannt', 'venue': '', 'rank': None}
        other = teams.get(away if team == home else home, {})
        return {'opponent': other.get('tn', 'Unbekannt'),
                'venue': 'Heim' if team == home else 'Auswärts', 'rank': number(other.get('cpl'))}

    def minutes(match):
        return number(str(match['mp']).replace("'", '')) if match.get('mp') is not None else None

    history = []
    for date, match in completed[-8:][::-1]:
        history.append({'date': date.astimezone(ZoneInfo('Europe/Berlin')).strftime('%d.%m.%Y'),
                        'points': number(match.get('p')), 'minutes': minutes(match),
                        'goals': number(match.get('g')), 'assists': number(match.get('a')),
                        # k is an event-code list, not a card count.
                        'cards': None, **opponent(match, str(match.get('pt') or profile.get('tid')))})
    fixtures = [{'date': date.astimezone(ZoneInfo('Europe/Berlin')).strftime('%d.%m.%Y, %H:%M'),
                 **opponent(match, str(profile.get('tid')))} for date, match in ordered
                if date >= now and match.get('mdst') == 0
                and str(profile.get('tid')) in (str(match.get('t1')), str(match.get('t2')))][:6]
    yellow, red = number(profile.get('y')), number(profile.get('r'))
    season_year = now.year if now.month >= 7 else now.year - 1
    current = [(d, m) for d, m in completed if d.year > season_year or (d.year == season_year and d.month >= 7)]
    recent = [number(m['p']) for _, m in current[-3:]]
    return {'history': history, 'fixtures': fixtures,
            'minutes': round(number(profile['sec']) / 60, 1) if number(profile.get('sec')) is not None else None,
            'goals': number(profile.get('g')), 'assists': number(profile.get('a')),
            'cards': f'{int(yellow)} Gelb / {int(red)} Rot' if yellow is not None and red is not None else None,
            'season': number(profile.get('ap')), 'l3': sum(recent) / len(recent) if recent else None,
            'recent': recent, 'detailsAt': now.isoformat()}
