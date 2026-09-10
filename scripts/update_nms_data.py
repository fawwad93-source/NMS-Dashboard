import json, os, re
from datetime import datetime, timezone
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

SHEET_ID = '1VdmdKDECLFNTonee-AqhyxHWQComjVAiXlXb9-7hMsE'
WORKSHEET = 'NMS Daily'
OUT = Path(__file__).resolve().parents[1] / 'nms-data.json'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

ERROR_RE = re.compile(r'^#(?:DIV/0!|REF!|VALUE!|N/A|NAME\?|NULL!|ERROR!)$', re.I)


def clean(v):
    return '' if v is None else str(v).strip()


def num(v):
    s = clean(v)
    if not s or ERROR_RE.match(s):
        return None
    s = re.sub(r'(?i)\b(?:Rs\.?|PKR)\b', '', s).replace(',', '').replace('%', '').strip()
    if s in {'-', '—'}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def date_iso(v):
    s = clean(v)
    if not s:
        return None
    # Common Google Sheet display formats used in NMS.
    for fmt in ('%d %b %Y', '%d %B %Y', '%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d', '%m/%d/%Y'):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass
    # Allow extra text around a date such as "8 Sep 2026" in a formatted table header.
    m = re.search(r'\b(\d{1,2})\s+([A-Za-z]{3,9})\s+(20\d{2})\b', s)
    if m:
        for fmt in ('%d %b %Y', '%d %B %Y'):
            try:
                return datetime.strptime(' '.join(m.groups()), fmt).date().isoformat()
            except ValueError:
                pass
    return None


def norm_header(v):
    return re.sub(r'\s+', ' ', clean(v).lower())


def find_idx(headers, predicates):
    for i, h in enumerate(headers):
        for p in predicates:
            if p(h):
                return i
    return -1


def parse(rows):
    current_date = None
    mapping = None
    items = []
    explicit_totals = {}

    metric_keys = ['sale','cogs','margin','returns','discount','profit','purchasing','receiving','stock','missedSale','missedCogs','missedProfit']

    def value(row, key):
        idx = mapping.get(key, -1)
        return num(row[idx]) if idx >= 0 and idx < len(row) else None

    def has_raw(row, key):
        idx = mapping.get(key, -1)
        return idx >= 0 and idx < len(row) and clean(row[idx]) != '' and not ERROR_RE.match(clean(row[idx]))

    for raw in rows:
        row = [clean(x) for x in raw]
        if not any(row):
            continue
        lower = [norm_header(x) for x in row]
        # A header row is identified by ITEMS + Sale. The date can be anywhere on that row.
        if 'items' in lower and 'sale' in lower:
            found_date = next((date_iso(x) for x in row if date_iso(x)), None)
            if found_date:
                current_date = found_date
            mapping = {
                'item': lower.index('items'),
                'sale': lower.index('sale'),
                'cogs': find_idx(lower, [lambda x: 'cost of goods' in x]),
                'margin': find_idx(lower, [lambda x: 'margin' in x]),
                'returns': find_idx(lower, [lambda x: x in ('return','returns')]),
                'discount': find_idx(lower, [lambda x: x == 'discount']),
                'profit': find_idx(lower, [lambda x: x == 'profit']),
                'purchasing': find_idx(lower, [lambda x: 'purchasing' in x]),
                'receiving': find_idx(lower, [lambda x: 'receiving' in x]),
                'stock': find_idx(lower, [lambda x: x == 'stock']),
                'missedSale': find_idx(lower, [lambda x: 'missed sale' in x]),
                'missedCogs': find_idx(lower, [lambda x: 'missed cog' in x]),
                'missedProfit': find_idx(lower, [lambda x: 'missed profit' in x]),
            }
            continue

        if not current_date or not mapping:
            continue
        ii = mapping['item']
        item_name = row[ii] if ii < len(row) else ''
        if not item_name:
            continue

        if item_name.lower() == 'total':
            explicit_totals[current_date] = {
                'date': current_date,
                'sale': value(row,'sale'),
                'cogs': value(row,'cogs'),
                'margin': value(row,'margin'),
                'returns': value(row,'returns'),
                'discount': value(row,'discount'),
                'profit': value(row,'profit'),
                'purchasing': value(row,'purchasing'),
                'receiving': value(row,'receiving'),
                'stock': value(row,'stock'),
                'missedSale': value(row,'missedSale'),
                'missedCogs': value(row,'missedCogs'),
                'missedProfit': value(row,'missedProfit'),
            }
            continue

        if item_name.lower() in {'items','#','no.','no','sr.','sr'}:
            continue
        # Ignore preformatted future category rows with no actual metric entered.
        if not any(has_raw(row, k) for k in metric_keys):
            continue

        sale = value(row,'sale')
        cogs = value(row,'cogs')
        profit = value(row,'profit')
        if profit is None and sale is not None and cogs is not None:
            profit = sale - cogs
        margin = value(row,'margin')
        if margin is None and sale not in (None,0) and profit is not None:
            margin = profit / sale * 100
        items.append({
            'date': current_date,
            'item': item_name,
            'sale': sale or 0,
            'cogs': cogs or 0,
            'margin': margin,
            'returns': value(row,'returns'),
            'discount': value(row,'discount'),
            'profit': profit,
            'purchasing': value(row,'purchasing'),
            'receiving': value(row,'receiving'),
            'stock': value(row,'stock'),
            'missedSale': value(row,'missedSale'),
            'missedCogs': value(row,'missedCogs'),
            'missedProfit': value(row,'missedProfit'),
        })

    dates = sorted({r['date'] for r in items} | set(explicit_totals))
    totals = []
    for d in dates:
        day_items = [r for r in items if r['date'] == d]
        if not day_items and d not in explicit_totals:
            continue
        summed = {}
        for key in ('sale','cogs','returns','discount','profit','purchasing','receiving','missedSale','missedCogs','missedProfit'):
            vals = [r.get(key) for r in day_items if r.get(key) is not None]
            summed[key] = sum(vals) if vals else None
        base = explicit_totals.get(d, {'date': d})
        total = {'date': d}
        for key in ('sale','cogs','returns','discount','profit','purchasing','receiving','stock','missedSale','missedCogs','missedProfit'):
            v = base.get(key)
            if v is None and key != 'stock':
                v = summed.get(key)
            if key in ('returns','discount','purchasing') and v is None:
                v = 0
            total[key] = v
        if total['sale'] is None:
            total['sale'] = 0
        if total['cogs'] is None:
            total['cogs'] = 0
        if total['profit'] is None:
            total['profit'] = total['sale'] - total['cogs']
        margin = base.get('margin')
        total['margin'] = margin if margin is not None else (total['profit'] / total['sale'] * 100 if total['sale'] else 0)
        # Keep only days with actual entered business data.
        actual = any((total.get(k) not in (None, 0)) for k in ('sale','cogs','profit','purchasing','receiving','stock','missedSale','missedCogs','missedProfit')) or bool(day_items)
        if actual:
            totals.append(total)

    if not totals and not items:
        raise RuntimeError('No NMS daily data was detected in the worksheet.')

    # Only keep item rows belonging to dates we publish.
    allowed = {t['date'] for t in totals}
    items = [r for r in items if r['date'] in allowed]
    latest = max(allowed) if allowed else None
    return {
        'meta': {
            'source': 'google-service-account',
            'sheetId': SHEET_ID,
            'worksheet': WORKSHEET,
            'latestDate': latest,
            'generatedAt': datetime.now(timezone.utc).isoformat()
        },
        'items': items,
        'totals': totals
    }


def main():
    raw = os.environ.get('GOOGLE_CREDENTIALS', '').strip()
    if not raw:
        raise RuntimeError('Missing GOOGLE_CREDENTIALS GitHub secret.')
    info = json.loads(raw)
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    client = gspread.authorize(creds)
    ws = client.open_by_key(SHEET_ID).worksheet(WORKSHEET)
    rows = ws.get_all_values()
    data = parse(rows)
    OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f"Wrote {OUT.name}: {len(data['totals'])} days, {len(data['items'])} category rows; latest={data['meta']['latestDate']}")

if __name__ == '__main__':
    main()
