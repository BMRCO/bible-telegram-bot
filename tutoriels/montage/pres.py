"""Video de presentation de LaBible.app (Short 1080x1920, voix du Henri).
Usage : python3 pres.py   (voix dans voix/ep11_<i>.mp3)"""
import serie
from serie import (Ep, P_ecran, P_image, P_fin, B, centre_de, centre, eclaircir, lignes, F, GAR, ROB, CREME,
                   rendre)
from PIL import ImageDraw

serie.SERIE = "LaBible.app"


def P_ouverture(dur=3.0):
    def f(ep, t):
        im = ep.fond.copy(); d = ImageDraw.Draw(im)
        centre(d, "LaBible.app", 760, F(GAR, 140), CREME)
        d.rounded_rectangle([540 - 70, 945, 540 + 70, 951], 3, fill=ep.acc)
        centre(d, "La Bible Louis Segond 1910", 990, F(GAR, 60), eclaircir(ep.acc, 0.2))
        return im
    return (dur, f)


def presentation():
    return Ep(11, "La Bible Louis Segond 1910", (226, 197, 122), [
        P_ouverture(),
        P_ecran("l3_texte", 700, "66 livres, 1 189 chapitres, 31 102 versets."),
        P_ecran("l5_clair", 420, "Gratuite. Sans publicité, sans compte."),
        P_ecran("i2_page", 400, "Même sans internet."),
        P_ecran("t2_barre", B("t2_barre", "bar")[1], "Écouter, copier, partager un verset."),
        P_ecran("j2_ouvert", 420, "Un nouveau verset chaque jour."),
        P_ecran("p1_plan", 330, "Toute la Bible en un an."),
        P_ecran("a1_audio", 340, "Bible audio, versets par thème, quiz."),
        P_image("j3_image.jpg", "Domaine public, pour tous."),
        P_fin()])


if __name__ == "__main__":
    ep = presentation()
    rendre(ep)
