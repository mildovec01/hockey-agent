import time
import sys
from tools.discord_bot import start_bot_thread

def main():
    print("=" * 50)
    print("  HockeyBot – Live Hockey Agent")
    print("=" * 50)

    bot_thread = start_bot_thread()

    print("[Main] HockeyBot běží. Ctrl+C pro ukončení.\n")

    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("\n[Main] Ukončuji...")


if __name__ == "__main__":
    main()