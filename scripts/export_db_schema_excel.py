import os
import sqlite3
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment

ROOT = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(ROOT, 'ratings.db')
OUT_PATH = os.path.join(ROOT, 'database_schema.xlsx')


def get_tables(conn):
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
    return [r[0] for r in cur.fetchall()]


def table_info(conn, table):
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    cols = cur.fetchall()
    return [
        {
            'cid': c[0],
            'name': c[1],
            'type': c[2],
            'notnull': bool(c[3]),
            'dflt_value': c[4],
            'pk': bool(c[5]),
        }
        for c in cols
    ]


def foreign_keys(conn, table):
    cur = conn.cursor()
    cur.execute(f"PRAGMA foreign_key_list({table})")
    rows = cur.fetchall()
    return [
        {
            'id': r[0],
            'seq': r[1],
            'table': r[2],
            'from': r[3],
            'to': r[4],
            'on_update': r[5],
            'on_delete': r[6],
            'match': r[7],
        }
        for r in rows
    ]


def autosize(ws):
    for col in ws.columns:
        max_len = 0
        col_letter = col[0].column_letter
        for cell in col:
            val = str(cell.value) if cell.value is not None else ''
            max_len = max(max_len, len(val))
        ws.column_dimensions[col_letter].width = min(max(10, max_len + 2), 60)


def main():
    if not os.path.exists(DB_PATH):
        raise SystemExit(f"Database not found: {DB_PATH}")

    wb = Workbook()
    # Remove default sheet
    wb.remove(wb.active)

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        tables = get_tables(conn)
        # Ensure preferred order if present
        preferred = ['users', 'games', 'user_scores']
        ordered = [t for t in preferred if t in tables] + [t for t in tables if t not in preferred]

        header_font = Font(bold=True)
        center = Alignment(horizontal='center')

        for t in ordered:
            ws = wb.create_sheet(title=t)
            ws.append(['Column', 'Type', 'Not Null', 'Default', 'Primary Key'])
            for cell in ws[1]:
                cell.font = header_font
                cell.alignment = center

            for col in table_info(conn, t):
                ws.append([
                    col['name'],
                    col['type'],
                    'YES' if col['notnull'] else 'NO',
                    col['dflt_value'],
                    'YES' if col['pk'] else 'NO',
                ])
            autosize(ws)

        # Relationships sheet
        ws_rel = wb.create_sheet(title='Relationships')
        ws_rel.append(['From Table', 'From Column', 'To Table', 'To Column', 'On Update', 'On Delete'])
        for cell in ws_rel[1]:
            cell.font = header_font
            cell.alignment = center

        for t in ordered:
            for fk in foreign_keys(conn, t):
                ws_rel.append([t, fk['from'], fk['table'], fk['to'], fk['on_update'], fk['on_delete']])
        autosize(ws_rel)

    wb.save(OUT_PATH)
    print(f"Wrote: {OUT_PATH}")


if __name__ == '__main__':
    main()
