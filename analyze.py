from datetime import datetime

def get_league_name(event):
    league = event.get("league")
    if league:
        return league.get("name") or league.get("abbreviation") or league.get("shortName")
    return "Inconnue"

def analyze_match(event):
    home = event["competitions"][0]["competitors"][0]
    away = event["competitions"][0]["competitors"][1]

    # Statistiques basiques
    stats_home = home.get("statistics", {})
    stats_away = away.get("statistics", {})

    # Forme récente & H2H simplifiée
    recent_home = stats_home.get("form", "N/A")
    recent_away = stats_away.get("form", "N/A")
    h2h = stats_home.get("h2h", "N/A")

    # Comparaison simple pour pronostic
    score_dom = 0
    score_ext = 0

    # Exemple : tirs
    home_shots = stats_home.get("shots", 0)
    away_shots = stats_away.get("shots", 0)
    if home_shots > away_shots:
        score_dom += 1
    else:
        score_ext += 1

    # Possession
    home_poss = stats_home.get("possession", 50)
    away_poss = stats_away.get("possession", 50)
    if home_poss > away_poss:
        score_dom += 1
    else:
        score_ext += 1

    # Buts marqués
    home_goals = home.get("score", 0)
    away_goals = away.get("score", 0)
    if home_goals > away_goals:
        score_dom += 2
    elif home_goals < away_goals:
        score_ext += 2
    else:
        score_dom += 1
        score_ext += 1

    # Confiance
    total = score_dom + score_ext
    confiance = round((score_dom if score_dom > score_ext else score_ext) / max(total,1) * 10, 1)

    # Pronostic final
    if score_dom > score_ext:
        pronostic = f"{home['team']['displayName']} gagne"
    elif score_dom < score_ext:
        pronostic = f"{away['team']['displayName']} gagne"
    else:
        pronostic = "Match nul"

    # Message détaillé
    return {
        "league": get_league_name(event),
        "home_team": home["team"]["displayName"],
        "away_team": away["team"]["displayName"],
        "score": f"{home_goals}-{away_goals}",
        "stats": {
            "tirs": f"{home_shots} - {away_shots}",
            "possession": f"{home_poss}% - {away_poss}%",
            "form": f"{recent_home} - {recent_away}",
            "h2h": h2h
        },
        "pronostic": pronostic,
        "confiance": confiance
    }
