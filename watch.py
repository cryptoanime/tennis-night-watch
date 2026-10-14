import argparse
import json
import logging
import os
import re
import smtplib
import ssl
import time
from datetime import datetime, timezone, timedelta
from email.message import EmailMessage
from pathlib import Path

BASE = Path(__file__).resolve().parent
JST = timezone(timedelta(hours=9))
ENTRY = 'https://www.e-shisetsu.e-aichi.jp/sp/index.jsp'


def changed(old, current):
    return [n for n, value in current.items() if value == '○' and old.get(n) != '○']


def atomic_save(path, data):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def scan():
    from playwright.sync_api import sync_playwright
    date = datetime.now(JST).date()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(30000)
        def link(name):
            page.get_by_role('link', name=name, exact=True).click()
        page.goto(ENTRY)
        link('施設空き状況')
        link('施設から')
        link('豊川市')
        page.get_by_role('textbox').fill('豊川公園')
        page.get_by_role('button', name='検索', exact=True).click()
        link('豊川公園庭球場（オーエスジード')
        found = {}
        for n in range(1, 13):
            if n == 11:
                link('次へ')
            full = str(n).translate(str.maketrans('0123456789', '０１２３４５６７８９'))
            name = 'テニスコート' + full
            link(name)
            button = page.get_by_role('button', name='検索開始', exact=True)
            button.wait_for(state='visible')
            page.get_by_role('combobox').nth(0).select_option(label=f'{date.month:02}')
            page.get_by_role('combobox').nth(1).select_option(label=f'{date.day:02}')
            button.click()
            page.get_by_role('heading', name='空き情報', exact=True).wait_for(state='visible')
            text = page.locator('body').inner_text()
            expected = rf'{date.year}\s*年\s*{date.month}\s*月\s*{date.day}\s*日'
            if name not in text or not re.search(expected, text):
                raise RuntimeError('対象コート・日付の確認に失敗しました')
            match = re.search(r'夜間\s*([○×])', text)
            if not match:
                raise RuntimeError(f'{name}: 夜間の表示が読めません')
            found[str(n)] = match.group(1)
            link('もどる')
            page.get_by_role('button', name='検索開始', exact=True).wait_for(state='visible')
            link('もどる')
            page.get_by_role('link', name=name, exact=True).wait_for(state='visible')
        browser.close()
    if datetime.now(JST).date() != date:
        raise RuntimeError('日付が変わったため次回再確認します')
    return date.isoformat(), found


def mail(config, subject, body):
    msg = EmailMessage()
    msg['From'] = config['smtp_user']
    msg['To'] = config['notify_to']
    msg['Subject'] = subject
    msg.set_content(body)
    with smtplib.SMTP(config['smtp_host'], config['smtp_port'], timeout=30) as smtp:
        smtp.ehlo()
        smtp.starttls(context=ssl.create_default_context())
        smtp.ehlo()
        smtp.login(config['smtp_user'], config['smtp_password'])
        smtp.send_message(msg)


def main():
    args = argparse.ArgumentParser()
    args.add_argument('--once', action='store_true', help='1回確認し表示のみ。メール・状態更新なし')
    args.add_argument('--test-email', action='store_true', help='テストメールを1通送る')
    args.add_argument('--scheduled', action='store_true', help='クラウド用：確認・通知を1回実行して終了')
    opt = args.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    config = json.loads((BASE / 'config.json').read_text(encoding='utf-8'))
    for key in ['smtp_user', 'smtp_password', 'notify_to']:
        if os.environ.get(key.upper()):
            config[key] = os.environ[key.upper()]
    if opt.test_email:
        mail(config, 'テニス夜間空き通知：接続テスト', 'テスト通知です。監視の開始通知ではありません。')
        print('テストメール送信完了')
        return
    if not opt.once and any(not config.get(k) for k in ['smtp_host', 'smtp_user', 'smtp_password', 'notify_to']):
        raise SystemExit('config.json のメール設定を入力してください。パスワードはチャットに送らないでください。')
    state_path = BASE / 'state.json'
    state = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {}
    interval = max(300, int(config.get('interval_seconds', 300)))
    failures = 0
    while True:
        start = time.monotonic()
        try:
            # 夜間終了後は監視しない。開始・終了時間は設定変更可。
            hour = datetime.now(JST).hour
            if not opt.once and not config.get('monitor_start_hour', 0) <= hour < config.get('monitor_end_hour', 21):
                if opt.scheduled:
                    return
                time.sleep(60)
                continue
            day, courts = scan()
            logging.info('%s 夜間 %s', day, courts)
            if opt.once:
                return
            old = state.get('courts', {}) if state.get('date') == day else {}
            available = changed(old, courts)
            if available:
                body = f'豊川公園庭球場\n{day}\n夜間に空きが出ました。\nコート：' + '、'.join(available)
                body += '\n確認時刻：' + datetime.now(JST).strftime('%Y/%m/%d %H:%M:%S')
                body += '\n予約サイト：' + ENTRY + '\n空きは確認時点の情報です。予約前に再確認してください。'
                mail(config, '🎾 テニスコート：本日の夜間に空きがあります', body)
            # 送信失敗時は更新せず次回再送。初回に既存の空きがあれば通知する。
            state = {'date': day, 'courts': courts, 'checked_at': datetime.now(JST).isoformat()}
            atomic_save(state_path, state)
            failures = 0
            if opt.scheduled:
                return
        except Exception as exc:
            failures += 1
            logging.error('確認・送信失敗 (%s回): %s', failures, type(exc).__name__)
            # 読み込み失敗を「空き」と誤判定しない。連続失敗時はエラー通知。
            if failures == 3 and not opt.once:
                try:
                    mail(config, 'テニス空き監視：確認に失敗しています', '3回連続で確認または通知に失敗しました。PCの画面・ログを確認してください。')
                except Exception:
                    logging.error('エラー通知も送信できませんでした')
            if opt.once or opt.scheduled:
                raise
        time.sleep(max(1, interval - (time.monotonic() - start)))


if __name__ == '__main__':
    main()
