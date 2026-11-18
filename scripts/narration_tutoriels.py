"""Voix du narrateur (Henri, edge-tts, debit -8 %) des tutoriels.
Une phrase = un fichier : sortie/ep<NN>_<i>.mp3. Usage : python narration_tutoriels.py <ep> [<ep>...] sortie"""
import asyncio, json, os, sys
import edge_tts
import edge_tts.communicate as _comm

VOIX, DEBIT = "fr-FR-HenriNeural", "-8%"


def _mkssml_fr(tc, txt):
    # meme SSML que psaume_meditation.py : langue imposee en francais
    if isinstance(txt, bytes):
        txt = txt.decode("utf-8")
    return ("<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='fr-FR'>"
            f"<voice name='{tc.voice}'><prosody pitch='{tc.pitch}' rate='{tc.rate}' volume='{tc.volume}'>"
            f"{txt}</prosody></voice></speak>")


async def main(eps, sortie):
    _comm.mkssml = _mkssml_fr
    data = json.load(open("tutoriels/narration.json", encoding="utf-8"))
    os.makedirs(sortie, exist_ok=True)
    for ep in eps:
        for i, phrase in enumerate(data[str(ep)]):
            if not phrase:
                continue
            out = os.path.join(sortie, f"ep{int(ep):02d}_{i}.mp3")
            for essai in range(3):
                try:
                    await edge_tts.Communicate(phrase.replace("’", "'"), VOIX, rate=DEBIT).save(out)
                    break
                except Exception as e:
                    print(f"⚠️  {out} : {e}")
                    await asyncio.sleep(3)
            print("ok", out)

if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:-1], sys.argv[-1]))
