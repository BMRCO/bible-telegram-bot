"""Voix du narrateur (Henri, edge-tts, debit -8 %) des tutoriels.
Une phrase = un fichier : sortie/ep<NN>_<i>.mp3. Usage : python narration_tutoriels.py <ep> [<ep>...] sortie"""
import asyncio, json, os, sys
import edge_tts
import edge_tts.communicate as _comm

VOIX = "fr-FR-HenriNeural"
DEBIT = os.environ.get("DEBIT_TUTO", "").strip() or "-16%"
# VOIX_TUTO=Algieba (ou un autre nom Chirp 3 HD) : voix Google, chave GOOGLE_TTS_KEY
# VOIX_TUTO=piper:<modele> (ex. piper:fr_FR-tom-medium) : voix Piper, modele dans PIPER_MODELE,
#   sortie en WAV (convertie en MP3 au montage)
VOIX_TUTO = os.environ.get("VOIX_TUTO", "").strip()
PIPER = VOIX_TUTO.startswith("piper:")
GOOGLE = "" if PIPER else VOIX_TUTO
_piper = None


def piper(phrase, out):
    """Une phrase en WAV avec la voix Piper ; refuse une voix qui avalerait des sons."""
    global _piper
    import wave
    from piper import PiperVoice, SynthesisConfig
    if _piper is None:
        _piper = PiperVoice.load(os.environ["PIPER_MODELE"])
        if "\u0303" not in _piper.config.phoneme_id_map:
            sys.exit("ECHEC : voix sans tilde combinant, elle avalerait les nasales.")
    carte = _piper.config.phoneme_id_map
    perdus = sum(1 for ph in _piper.phonemize(phrase) for p in ph if p not in carte)
    if perdus:
        print(f"⚠️  {out} : {perdus} phoneme(s) inconnu(s) du modele")
    cfg = SynthesisConfig(length_scale=float(os.environ.get("PIPER_LENTEUR") or 1.0))
    with wave.open(out, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(_piper.config.sample_rate)
        for chunk in _piper.synthesize(phrase, syn_config=cfg):
            w.writeframes(chunk.audio_int16_bytes)


def google(phrase, out):
    import base64, requests
    r = requests.post("https://texttospeech.googleapis.com/v1/text:synthesize",
                      headers={"X-Goog-Api-Key": os.environ["GOOGLE_TTS_KEY"].strip(),
                               "Content-Type": "application/json; charset=utf-8"},
                      data=json.dumps({"input": {"text": phrase.replace("Éternel", "Eternel")},
                                       "voice": {"languageCode": "fr-FR", "name": f"fr-FR-Chirp3-HD-{GOOGLE}"},
                                       "audioConfig": {"audioEncoding": "MP3", "speakingRate": 0.92}}), timeout=120)
    r.raise_for_status()
    open(out, "wb").write(base64.b64decode(r.json()["audioContent"]))


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
            out = os.path.join(sortie, f"ep{int(ep):02d}_{i}.{'wav' if PIPER else 'mp3'}")
            for essai in range(3):
                try:
                    if PIPER:
                        piper(phrase.replace("’", "'"), out)
                    elif GOOGLE:
                        google(phrase.replace("’", "'"), out)
                    else:
                        await edge_tts.Communicate(phrase.replace("’", "'"), VOIX, rate=DEBIT).save(out)
                    break
                except Exception as e:
                    print(f"⚠️  {out} : {e}")
                    await asyncio.sleep(3)
            print("ok", out, VOIX_TUTO or "Henri")

if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:-1], sys.argv[-1]))
