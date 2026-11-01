# League Tool

**English** · [Español](#español)

A desktop app (Python + CustomTkinter) that automates the pre-game phase of the League of Legends client through the local client API (LCU). It never touches the match itself.

## Features

- **Accept match** automatically (configurable delay).
- **Pick**: declares your preferred champion early (so your team sees it), then selects and locks it on your turn. Uses the first champion of your list that is still available.
- **Ban**: on your ban turn, waits a configurable delay, selects and confirms the first available champion of your list. Skips champions your allies declared and your own picks.
- **Summoner spells** per role.
- **Runes**: your own presets (assignable to a role or to specific champions) or the **runes recommended by the client itself**. Order: champion preset → client recommendation → role preset. Written to a page named `LT - <name>`; if you have no free rune slot, that page replaces your last editable one (can be turned off in Settings).
- Per-role lists (Top, Jungle, Mid, ADC, Support); a role without a list uses **Default**.
- **Live suggestions while you play** (local Live Client API, no Riot key needed): who to focus and why, objective reminders (dragons, Voidgrubs, Herald, Baron) and situational items based on the enemy team composition. Shown in the **Live** tab and in a small always-on-top overlay you can toggle with `Ctrl+Shift+L` (configurable in Settings). Play in **borderless mode** — exclusive fullscreen blocks every app's overlay.
- **Adaptive builds**: a core build for your champion class (marksman, assassin, mage, fighter, tank, support…) plus boots that adapt to the enemy team — Mercury's against heavy CC/AP, Steelcaps against heavy AD — followed by the situational items. Recommendations track the game: what you already bought drops off (including component→upgrade), composition items unlock after laning phase, and full builds get an elixir reminder. Always in the overlay's items section.
- **Enemy scouting on the loading screen** (needs a Riot API key in Settings): for each rival you see their Riot ID, solo-queue rank with LP and winrate, and their mastery with the champion they picked. Results are cached, so dodged lobbies don't waste the rate limit.
- **Post-game analysis** (Riot API): when the match ends, the **Analysis** tab shows your KDA, damage share, CS/min, vision, team gold difference at minute 15, automatic highlights (what went well and what to improve) and the full 10-player scoreboard.
- **English and Spanish** UI, switchable in Settings.

## Download

Grab the latest build from the [Releases](../../releases) page:

| Platform | File |
|---|---|
| Windows | `LeagueTool-windows-x64.exe` |
| macOS Apple Silicon (M1/M2/M3/M4) | `LeagueTool-macOS-apple-silicon-arm64.dmg` |
| macOS Intel | `LeagueTool-macOS-intel-x86_64.dmg` |

The builds are not code-signed. Windows SmartScreen may warn you: choose *More info → Run anyway*. On macOS, open the DMG, drag the app to *Applications*, then right-click it and choose *Open* the first time (or run `xattr -dr com.apple.quarantine "/Applications/LeagueTool.app"`).

## Run from source

```bash
pip install -r requirements.txt
python main.py
```

Open the League client whenever you like; the app detects it by itself. Champion, item and rune data is downloaded from Data Dragon (internet needed the first time, cached afterwards). Settings are stored in `%LOCALAPPDATA%\LeagueTool\config.json` (Windows) or `~/Library/Application Support/LeagueTool/config.json` (macOS).

Tests (no client needed): `python -m unittest discover -s tests -t .`

## Notes

- The LCU API is unofficial and can change at any time. Riot asks that apps using it are registered on the [developer portal](https://developer.riotgames.com/) and only use approved endpoints; read their [policy](https://developer.riotgames.com/docs/lol) before distributing a build.
- This project is not endorsed by Riot Games and does not reflect the views or opinions of Riot Games or anyone officially involved in producing or managing Riot Games properties. League of Legends and Riot Games are trademarks or registered trademarks of Riot Games, Inc.

---

# Español

Aplicación de escritorio (Python + CustomTkinter) que automatiza la fase previa a la partida en el cliente de League of Legends usando la API local del cliente (LCU). No toca la partida en sí.

## Qué hace

- **Aceptar partida** automáticamente (con espera configurable).
- **Pick**: marca tu campeón preferido en la declaración (para que tu equipo lo vea) y luego lo selecciona y bloquea en tu turno. Usa el primer campeón de tu lista que siga disponible.
- **Ban**: en tu turno de ban espera un retraso configurable, selecciona y confirma el primer campeón disponible de tu lista. Salta lo que tus aliados han declarado y tus propios picks.
- **Hechizos de invocador** según el rol.
- **Runas**: presets propios (asignables a un rol o a campeones concretos) o las **runas recomendadas por el propio cliente**. Orden: preset del campeón → recomendación del cliente → preset del rol. Se escriben en una página llamada `LT - <nombre>`; si no tienes hueco libre, esa página reemplaza tu última página editable (se puede desactivar en Ajustes).
- Listas por rol (Top, Jungla, Mid, ADC, Support); un rol sin lista usa **Predeterminado**.
- **Sugerencias en tiempo real mientras juegas** (Live Client API local, sin clave de Riot): a quién focusear y por qué, recordatorios de objetivos (dragones, Voidgrubs, Heraldo, Barón) e ítems situacionales según la composición enemiga. Se ven en la pestaña **En vivo** y en un pequeño overlay siempre visible que se muestra/oculta con `Ctrl+Shift+L` (configurable en Ajustes). Juega en **modo sin bordes**: la pantalla completa exclusiva bloquea el overlay de cualquier app.
- **Builds adaptativas**: build núcleo según la clase de tu campeón (tirador, asesino, mago, luchador, tanque, apoyo…) más botas que se adaptan al equipo rival — Mercurio contra mucho CC/AP, Punteras de acero contra mucho AD — seguidas de los ítems situacionales. Las recomendaciones siguen la partida: lo que ya compraste desaparece (incluido componente→mejora), los ítems de composición se activan tras la fase de líneas y con build completa te recuerda el elixir. Siempre en la sección de ítems del overlay.
- **Info de rivales en la pantalla de carga** (requiere una clave de Riot API en Ajustes): para cada rival ves su Riot ID, su rango en soloq con LP y winrate, y su maestría con el campeón que eligió. Los resultados se cachean, así que las salas canceladas no gastan tu límite de peticiones.
- **Análisis post-partida** (Riot API): al terminar la partida, la pestaña **Análisis** muestra tu KDA, % de daño de tu equipo, CS/min, visión, diferencia de oro de equipo al minuto 15, puntos clave automáticos (qué salió bien y qué mejorar) y el marcador completo de los 10 jugadores.
- Interfaz en **español e inglés**, cambiable en Ajustes.

## Descarga

Descarga la última versión desde [Releases](../../releases):

| Plataforma | Archivo |
|---|---|
| Windows | `LeagueTool-windows-x64.exe` |
| macOS Apple Silicon (M1/M2/M3/M4) | `LeagueTool-macOS-apple-silicon-arm64.dmg` |
| macOS Intel | `LeagueTool-macOS-intel-x86_64.dmg` |

Las versiones no están firmadas. Windows SmartScreen puede avisarte: elige *Más información → Ejecutar de todas formas*. En macOS abre el DMG, arrastra la app a *Aplicaciones* y la primera vez haz clic derecho → *Abrir* (o ejecuta `xattr -dr com.apple.quarantine "/Applications/LeagueTool.app"`).

## Ejecutar desde el código

```bash
pip install -r requirements.txt
python main.py
```

Abre el cliente de League cuando quieras; la app lo detecta sola. Los datos de campeones, ítems y runas se descargan de Data Dragon (internet la primera vez, luego quedan en caché). La configuración se guarda en `%LOCALAPPDATA%\LeagueTool\config.json` (Windows) o `~/Library/Application Support/LeagueTool/config.json` (macOS).

Tests (sin cliente): `python -m unittest discover -s tests -t .`

## Notas

- La API LCU no es oficial y puede cambiar en cualquier momento. Riot pide registrar las apps que la usan en el [portal de desarrolladores](https://developer.riotgames.com/) y usar solo endpoints aprobados; lee su [política](https://developer.riotgames.com/docs/lol) antes de distribuir una versión.
- Este proyecto no está respaldado por Riot Games ni refleja las opiniones de Riot Games ni de nadie involucrado oficialmente en la producción o gestión de sus propiedades. League of Legends y Riot Games son marcas comerciales o registradas de Riot Games, Inc.
