from fetch import fetch_today_matches
from analyze import analyze_match
from telegram import send_telegram

def main():
    print("🚀 Bot démarré")
    matches = fetch_today_matches()
    print(f"[INFO] {len(matches)} matchs trouvés aujourd'hui")

    analyzed_matches = []
    for e in matches:
        try:
            analyzed = analyze_match(e)
            analyzed_matches.append(analyzed)

            # Construction message Telegram
            msg = f"🏆 {analyzed['league']}\n" \
                  f"⚽ {analyzed['home_team']} vs {analyzed['away_team']}\n" \
                  f"📊 Score : {analyzed['score']}\n\n" \
                  f"📈 Statistiques détaillées :\n" \
                  f"Tirs: {analyzed['stats']['tirs']}\n" \
                  f"Possession: {analyzed['stats']['possession']}\n" \
                  f"Forme récente: {analyzed['stats']['form']}\n" \
                  f"H2H: {analyzed['stats']['h2h']}\n\n" \
                  f"🔮 Pronostic : {analyzed['pronostic']}\n" \
                  f"🎯 Confiance : {analyzed['confiance']}/10"
            send_telegram(msg)
        except Exception as err:
            print(f"[ERREUR] {err}")

if __name__ == "__main__":
    main()
