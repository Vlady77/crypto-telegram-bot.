name: Telegram Smoke Test
on:
  workflow_dispatch: {}
jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - run: python - <<'PY'
          import os, requests
          token=os.environ["TELEGRAM_BOT_TOKEN"]
          chat=os.environ["TELEGRAM_CHAT_ID"]
          r=requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          data={"chat_id":chat,"text":"Action test ✅ from GitHub"})
          print("HTTP", r.status_code); print(r.text)
          r.raise_for_status()
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
