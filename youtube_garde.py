"""youtube_garde.py : refuse d'envoyer une video si le jeton YouTube pointe
vers une autre chaine que celle de LaBible.app.

La chaine LaBible.app compte des centaines de videos. Un jeton obtenu sur le
mauvais compte ou la mauvaise chaine (chaine vide creee par Google) passerait
sans erreur et publierait au mauvais endroit : on verifie donc le nombre de
videos avant chaque envoi. L'exception levee suit le meme chemin qu'un jeton
expire : les autres plateformes continuent.
"""

MIN_VIDEOS = 100


def verifier_chaine(yt):
    items = yt.channels().list(part="snippet,statistics", mine=True).execute().get("items", [])
    if not items:
        raise RuntimeError("jeton YouTube sans chaine : envoi annule")
    n = int(items[0].get("statistics", {}).get("videoCount", 0) or 0)
    if n < MIN_VIDEOS:
        titre = items[0].get("snippet", {}).get("title", "?")
        raise RuntimeError(f"jeton YouTube lie a la chaine « {titre} » ({n} videos), "
                           f"pas a LaBible.app : envoi annule")
    return items[0]["id"]
