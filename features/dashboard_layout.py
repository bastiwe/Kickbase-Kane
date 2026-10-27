"""Validated, versioned dashboard designs. No executable HTML/CSS is stored."""
import json
import math
import re
from urllib.parse import urlsplit


def empty_design():
    return {'version': 1, 'revision': 0, 'enabled': False, 'desktop': None, 'mobile': None}


def image_url(value):
    if not isinstance(value, str) or len(value) > 250_000:
        raise ValueError('Grafik ist zu groß (maximal 250 KB pro Grafik).')
    if not value:
        return value
    if re.fullmatch(r'data:image/(png|jpeg|webp|gif);base64,[A-Za-z0-9+/=]+', value):
        return value
    parsed = urlsplit(value)
    if parsed.scheme not in ('http', 'https') or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError('Grafiken benötigen eine HTTP(S)-Adresse oder eine hochgeladene Bilddatei.')
    return value


def validate_design(body):
    def text(value, limit=500):
        if not isinstance(value, str) or len(value) > limit:
            raise ValueError('Ungültiger Text im Layout.')
        return value

    def number(value, lo, hi, integer=False):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not lo <= value <= hi:
            raise ValueError('Ungültige Größe oder Position im Layout.')
        if integer and int(value) != value:
            raise ValueError('Das Kachelraster benötigt ganze Zahlen.')
        return value

    def color(value):
        if not isinstance(value, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', value):
            raise ValueError('Ungültige Farbe im Layout.')
        return value

    def changed(value):
        allowed = {'title', 'order', 'x', 'y', 'w', 'h', 'color', 'opacity', 'cardColumns', 'cardHeight',
                   'cardGap', 'cardColor', 'cardOpacity', 'text', 'source', 'url', 'background',
                   'backgroundOpacity', 'fontSize', 'bold', 'radius', 'zoom', 'imageY', 'align', 'fit', 'format'}
        if not isinstance(value, list) or any(not isinstance(key, str) or key not in allowed for key in value):
            raise ValueError('Ungültige Standardansicht-Anpassung.')
        return list(dict.fromkeys(value))

    if body.get('version') != 1 or not isinstance(body.get('enabled'), bool):
        raise ValueError('Unbekanntes Layoutformat.')
    result = {'version': 1, 'revision': number(body.get('revision'), 0, 1e12, True), 'enabled': body['enabled']}
    for mode in ('desktop', 'mobile'):
        layout = body.get(mode)
        if layout is None:
            result[mode] = None
            continue
        if not isinstance(layout, dict) or not isinstance(layout.get('tiles'), list) or len(layout['tiles']) > 80:
            raise ValueError('Maximal 80 Kacheln pro Ansicht erlaubt.')
        columns = number(layout.get('columns'), 1, 24, True)
        clean = {'columns': columns, 'rowHeight': number(layout.get('rowHeight'), 10, 150, True),
                 'gap': number(layout.get('gap'), 0, 40, True), 'tiles': []}
        native = layout.get('native') is True
        if native:
            clean['native'] = True
        tile_ids = set()
        sections = set()
        native_keys = set()
        for tile in layout['tiles']:
            if not isinstance(tile, dict) or not isinstance(tile.get('elements'), list) or len(tile['elements']) > 40:
                raise ValueError('Maximal 40 Elemente pro Kachel erlaubt.')
            item = {'id': text(tile.get('id'), 80), 'title': text(tile.get('title'), 100),
                    'x': number(tile.get('x'), 0, columns - 1, True), 'y': number(tile.get('y'), 0, 1000, True),
                    'w': number(tile.get('w'), 1, columns, True), 'h': number(tile.get('h'), 1, 30, True),
                    'color': color(tile.get('color')), 'opacity': number(tile.get('opacity'), 0, 1),
                    'collection': text(tile.get('collection', ''), 500), 'record': text(tile.get('record', ''), 200),
                    'elements': []}
            if item['x'] + item['w'] > columns or item['id'] in tile_ids:
                raise ValueError('Kachel liegt außerhalb des Rasters oder hat eine doppelte ID.')
            tile_ids.add(item['id'])
            if native:
                key = tile.get('nativeKey')
                if key not in ('budget', 'squad', 'forecast', 'history', 'managers', 'transfers', 'chances', 'roster', 'risks', 'market') or key in native_keys:
                    raise ValueError('Ungültiger oder doppelter Standardbereich.')
                native_keys.add(key)
                item.update(nativeKey=key, order=number(tile.get('order'), 0, 79, True), changed=changed(tile.get('changed', [])))
            if tile.get('section') is not None:
                section = tile['section']
                if section not in ('transfers', 'chances', 'roster', 'risks', 'market') or section in sections:
                    raise ValueError('Jeder Dashboard-Bereich darf nur eine Spielerkachel-Vorlage haben.')
                sections.add(section)
                item.update(section=section,
                            cardColumns=number(tile.get('cardColumns'), 1, 8, True),
                            cardHeight=number(tile.get('cardHeight'), 80, 600, True),
                            cardGap=number(tile.get('cardGap'), 0, 40, True),
                            cardColor=color(tile.get('cardColor')),
                            cardOpacity=number(tile.get('cardOpacity'), 0, 1))
                # Repeated templates must never bind to an individual player.
                item['collection'] = item['record'] = ''
            element_ids = set()
            for element in tile['elements']:
                if not isinstance(element, dict) or element.get('type') not in ('text', 'data', 'image'):
                    raise ValueError('Unbekannter Elementtyp.')
                e = {'id': text(element.get('id'), 80), 'type': element['type'],
                     'text': text(element.get('text', ''), 4000), 'source': text(element.get('source', ''), 1000),
                     'url': image_url(element.get('url', '')), 'color': color(element.get('color')),
                     'background': color(element.get('background')), 'backgroundOpacity': number(element.get('backgroundOpacity'), 0, 1),
                     'opacity': number(element.get('opacity'), 0, 1), 'fontSize': number(element.get('fontSize'), 8, 120),
                     'bold': bool(element.get('bold')), 'radius': number(element.get('radius'), 0, 100),
                     'zoom': number(element.get('zoom'), 1, 5), 'imageY': number(element.get('imageY'), 0, 100),
                     'x': number(element.get('x'), -300 if native else 0, 300 if native else 100), 'y': number(element.get('y'), -300 if native else 0, 300 if native else 100),
                     'w': number(element.get('w'), 1, 600 if native else 100), 'h': number(element.get('h'), 1, 600 if native else 100)}
                if (not native and (e['x'] + e['w'] > 100.01 or e['y'] + e['h'] > 100.01)) or e['id'] in element_ids:
                    raise ValueError('Element liegt außerhalb der Kachel oder hat eine doppelte ID.')
                if native:
                    e.update(nativeKey=text(element.get('nativeKey', ''), 80), label=text(element.get('label', ''), 100),
                             changed=changed(element.get('changed', [])))
                    if element.get('scope', 'tile') not in ('tile', 'row'):
                        raise ValueError('Ungültiger Elementbereich.')
                    e['scope'] = element.get('scope', 'tile')
                element_ids.add(e['id'])
                for key, choices in {'align': ('left', 'center', 'right'), 'fit': ('contain', 'cover'),
                                     'format': ('auto', 'number', 'euro', 'million', 'percent', 'date')}.items():
                    if element.get(key) not in choices:
                        raise ValueError('Ungültige Elementdarstellung.')
                    e[key] = element[key]
                item['elements'].append(e)
            clean['tiles'].append(item)
        result[mode] = clean
    if len(json.dumps(result).encode('utf-8')) > 1_800_000:
        raise ValueError('Layout ist zu groß. Bitte weniger oder kleinere Grafiken verwenden.')
    return result


def load_design(path):
    try:
        return validate_design(json.loads(path.read_text(encoding='utf-8')))
    except (OSError, ValueError, TypeError, AttributeError):
        return empty_design()
