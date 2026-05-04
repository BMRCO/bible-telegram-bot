# 🚀 LaBible.app — Expansão para 10 Categorias

## 📋 O que mudou

**Antes (5 categorias):**
- 🌿 Promesses, ✝️ Jésus, 🎵 Psaumes, 💡 Sagesse, 📯 Prophéties

**Agora (10 categorias):**
- 🌿 Promesses, ✝️ Jésus, 🎵 Psaumes, 💡 Sagesse, 📯 Prophéties
- 🛡️ **Protection Divine** (NOVO)
- 💫 **Espérance et Confiance** (NOVO)
- 🕊️ **Paix Intérieure** (NOVO)
- ❤️ **Amour de Dieu** (NOVO)
- 🙏 **Prière et Foi** (NOVO)

## ⏰ Novo schedule (UTC → França)

| UTC | FR | Categoria | Tipo |
|-----|-----|-----------|------|
| **5h** | 7h | 🛡️ **Protection Divine** | image (Matin) |
| 7h | 9h | 🌿 Promesse / 💫 Espérance (alterna) | reel |
| 11h | 13h | 💡 Sagesse / ❤️ Amour (alterna) | image |
| 13h | 15h | ✝️ Jésus / 🙏 Prière (alterna) | reel |
| 17h | 19h | 📯 Prophétie / 🕊️ Paix (alterna) | image |
| **19h** | 21h | 🎵 **Psaume du Soir** | reel |

**Estrutura emocional do dia:**
- 🌅 Manhã → Proteção (preparação para o dia)
- ☀️ Dia → variedade espiritual
- 🌙 Noite → Psaumes (paz, descanso)

A alternância entre 2 categorias por slot é feita por **dia par/ímpar** do ano — garante diversidade sem repetir.

## 📦 Ficheiros

```
labible-v2/
├── bot.py                       ← SUBSTITUIR no repo
├── publish.yml                  ← SUBSTITUIR em .github/workflows/
├── protection_curated.json      ← NOVO
├── esperance_curated.json       ← NOVO
├── paix_curated.json            ← NOVO
├── amour_curated.json           ← NOVO
└── priere_curated.json          ← NOVO
```

## 🚀 Instalação (5 min)

### 1️⃣ Repo `bible-telegram-bot` — adicionar JSONs

1. Vai a github.com/BMRCO/bible-telegram-bot
2. Faz upload destes 5 ficheiros para a **raiz do repo**:
   - `protection_curated.json`
   - `esperance_curated.json`
   - `paix_curated.json`
   - `amour_curated.json`
   - `priere_curated.json`

### 2️⃣ Substituir `bot.py`

1. Abre `bot.py` no GitHub
2. Substitui pelo novo `bot.py`
3. Commit

### 3️⃣ Substituir `publish.yml`

1. Vai a `.github/workflows/publish.yml`
2. Substitui pelo novo
3. Commit

### 4️⃣ Testar

Vai a **Actions → Publication automatique → Run workflow**, escolhe:
- **mode:** `image`
- **category:** `protection`

Deve publicar uma imagem 🛡️ Protection Divine sem erros.

## 🎨 Conteúdo dos JSONs

Cada JSON tem **20 versículos** curados:

### 🛡️ Protection Divine (20)
Psaumes 91, 121, 27, 18, 32, 34, 46, 61 + Ésaïe 41:10, 43:2, 54:17 + Proverbes 18:10 + Nahum 1:7 + 2 Thess 3:3 + 2 Tim 4:18

### 💫 Espérance et Confiance (20)
Jér 29:11 + Rom 8:28, 15:13, 5:5 + Héb 11:1, 6:19 + Lam 3:22-24 + És 40:31, 49:23 + 1 Pi 1:3 + Tite 2:13 + Mich 7:7 + Prov 23:18 + Rom 12:12 + Ps 39:7, 42:11, 71:14, 130:5

### 🕊️ Paix Intérieure (20)
Jean 14:27, 16:33 + Phil 4:6-7 + Ps 4:8, 3:5, 29:11, 34:14, 119:165 + És 26:3, 32:17, 9:6, 54:10 + Rom 5:1, 8:6, 14:17, 15:33 + Col 3:15 + 2 Thess 3:16 + Héb 12:14

### ❤️ Amour de Dieu (20)
Jean 3:16, 15:13 + Rom 5:8, 8:38-39 + 1 Jean 4:8-10, 4:16, 4:19, 3:1 + Éph 2:4-5, 3:18-19 + Jér 31:3 + És 49:15-16, 43:4 + Sophonie 3:17

### 🙏 Prière et Foi (20)
Mat 7:7-8, 6:6, 21:22 + Marc 11:24 + Luc 11:9, 18:1 + Jean 14:13-14, 15:7 + Phil 4:6 + 1 Thess 5:17 + Jacques 1:6, 5:16 + 1 Jean 5:14-15 + Héb 4:16, 11:1, 11:6 + Ps 145:18

## ⚙️ O que continua a funcionar

✅ Telegram, Facebook, Instagram, YouTube, Pinterest, Threads
✅ Modo manual via `workflow_dispatch`
✅ Holy Week (separado)
✅ Paraboles (separado)
✅ Link clicável `https://labible.app`
✅ CTA "Abonnez-vous pour plus de versets"

## 🔮 Próximos passos sugeridos

1. **Validar primeiro post** com cada categoria nova
2. **Confirmar IDs das playlists YouTube** para auto-adição (ainda pendente)
3. **Adicionar mais versículos** aos JSONs ao longo do tempo

🙏
