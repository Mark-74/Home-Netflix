"""One-time helper: generate a Telethon StringSession for get_new_url().

Telegram requires an interactive login (phone number + the code Telegram texts
you) the first time. That can't happen inside Docker, so run this ONCE on your
machine, then paste the printed string into the TG_SESSION env var.

Setup:
  1. Get api_id / api_hash from https://my.telegram.org -> API development tools
  2. pip install telethon
  3. python -m backend.scripts.tg_session
  4. Put the printed values in your environment / docker-compose, e.g.:

       TG_API_ID=1234567
       TG_API_HASH=abcdef0123456789abcdef0123456789
       TG_SESSION=<the long string this script prints>
       TG_CHANNEL=@the_channel_that_announces_the_domain
"""

from telethon import TelegramClient
from telethon.sessions import StringSession


def main() -> None:
    api_id = int(input("api_id: ").strip())
    api_hash = input("api_hash: ").strip()

    with TelegramClient(StringSession(), api_id, api_hash) as client:
        print("\nTG_SESSION=" + client.session.save())
        print("\nDone. Add the env vars above (plus TG_API_ID, TG_API_HASH, TG_CHANNEL).")


if __name__ == "__main__":
    main()
