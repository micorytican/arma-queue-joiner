"""English and Ukrainian UI text.

Each key maps to (English, Ukrainian). Ukrainian follows Windows: polite "ви",
sentence case. Keep the same {placeholders} in both columns; a test checks it.
"""

from __future__ import annotations

import ctypes

LANGUAGE_NAMES = {"en": "English", "uk": "Українська"}

STRINGS: dict[str, tuple[str, str]] = {
    # Main page
    "main.settings": ("Settings", "Налаштування"),
    "status.idle.title": ("Ready to join", "Можна починати"),
    "status.idle.text": (
        "Hover over Join in the server browser, then press {start}.",
        "Наведіть мишу на кнопку Join у списку серверів і натисніть {start}.",
    ),
    "status.countdown.title": ("Starting in {n}", "Старт через {n}"),
    "status.countdown.text": (
        "Move the mouse over the Join button in the game.",
        "Наведіть мишу на кнопку Join у грі.",
    ),
    "status.running.title": ("Trying to join", "Спроби приєднатися"),
    "status.running.text": (
        "{detail}. Press {stop} or move the mouse to stop.",
        "{detail}. Щоб зупинити, натисніть {stop} або поворушіть мишею.",
    ),
    "status.paused.title": ("Paused", "Пауза"),
    "status.success.title": ("You're in the queue", "Ви в черзі"),
    "status.success.text": ("{detail}. Keep the game open.", "{detail}. Не закривайте гру."),
    "status.error.title": ("Something went wrong", "Щось пішло не так"),
    "status.error.text": (
        "{detail}. Details are in the log on the Diagnostics page.",
        "{detail}. Подробиці є в журналі на сторінці «Діагностика».",
    ),
    "status.success.watching": (
        "{detail}. You'll get another alert when you're in the game.",
        "{detail}. Ще одне сповіщення прийде, коли ви будете в грі.",
    ),
    "status.joining.title": ("Joining the server", "Вхід на сервер"),
    "status.joining.text": (
        "The queue let you in. Loading {server}.",
        "Черга вас пропустила. Завантаження: {server}.",
    ),
    "status.in_game.title": ("You're in the game", "Ви в грі"),
    "status.in_game.text": ("On {server}.", "Сервер: {server}."),
    "status.queue_lost.title": ("Dropped out of the queue", "Вас викинуло з черги"),
    "status.queue_lost.text": (
        "The server removed you from the queue. Start again to rejoin.",
        "Сервер прибрав вас із черги. Почніть знову, щоб повернутися.",
    ),
    "button.start": ("Start", "Почати"),
    "button.stop": ("Stop", "Зупинити"),
    "button.cancel": ("Cancel", "Скасувати"),
    "button.start_again": ("Start again", "Почати знову"),
    "button.change": ("Change", "Змінити"),
    "button.clear": ("Clear", "Очистити"),
    "button.open": ("Open", "Відкрити"),
    "button.close": ("Close", "Закрити"),
    "button.back": ("Back", "Назад"),
    "toggle.on": ("On", "Увімк."),
    "toggle.off": ("Off", "Вимк."),
    "main.hotkeys": ("Hotkeys", "Гарячі клавіші"),
    "main.hotkeys.text": (
        "{start} starts at the mouse position, {stop} stops",
        "{start} запускає з позиції миші, {stop} зупиняє",
    ),
    "main.activity": ("Activity", "Події"),
    "main.activity.empty": (
        "Events from the current run show up here.",
        "Тут з'являтимуться події поточного запуску.",
    ),
    "update.available": ("Version {version} is available.", "Доступна версія {version}."),
    "update.download": ("Download", "Завантажити"),
    # Join loop (details and log lines)
    "state.starting": ("Starting", "Запуск"),
    "state.clicking": ("Clicking Join", "Натискання Join"),
    "state.server_full": ("Server full, trying again", "Сервер заповнений, нова спроба"),
    "state.confirming": ("Queue screen found, checking", "Знайдено екран черги, перевірка"),
    "state.waiting_focus": ("Waiting for the Arma Reforger window", "Очікування вікна Arma Reforger"),
    "state.stopped": ("Stopped", "Зупинено"),
    "state.stopped_mouse": ("Stopped because you moved the mouse", "Зупинено, бо ви поворушили мишею"),
    "state.success": ("Got in after {attempts}", "Спроб: {n}"),
    "state.error": ("{error}", "{error}"),
    "state.input_blocked": (
        "Windows blocked the clicks. If Arma Reforger runs as administrator, run Queue Joiner "
        "as administrator too",
        "Windows заблокувала кліки. Якщо Arma Reforger запущена від імені адміністратора, "
        "запустіть Queue Joiner так само",
    ),
    "log.target": ("Join button at {x}, {y}", "Кнопка Join: {x}, {y}"),
    "log.server_full": ("#{n} Server full, closing the dialog", "#{n} Сервер заповнений, закриття вікна"),
    "log.in_queue": ("#{n} In the queue", "#{n} У черзі"),
    "log.queue_lost": ("#{n} Queue screen disappeared, closing it", "#{n} Екран черги зник, закриття"),
    "log.no_dialog": ("#{n} No dialog appeared, trying again", "#{n} Вікно не з'явилося, нова спроба"),
    "log.mouse_moved": ("You moved the mouse, stopping", "Ви поворушили мишею, зупинка"),
    "log.waiting_focus": (
        "Arma Reforger isn't the active window, waiting",
        "Arma Reforger не на передньому плані, очікування",
    ),
    "log.focus_back": (
        "Arma Reforger is active again, continuing",
        "Arma Reforger знову активна, продовження",
    ),
    "log.esc_not_found": (
        "ESC button not found on screen, pressing the key instead",
        "Кнопку ESC на екрані не знайдено, натискання клавіші",
    ),
    "log.error": ("Error: {error}", "Помилка: {error}"),
    "log.settings_failed": ("Couldn't save settings: {error}", "Не вдалося зберегти налаштування: {error}"),
    "log.notify_failed": (
        "Couldn't send the {channel} notification: {error}",
        "Не вдалося надіслати сповіщення ({channel}): {error}",
    ),
    "log.test_sent": ("Test notification sent ({channel})", "Тестове сповіщення надіслано ({channel})"),
    # Settings
    "settings.title": ("Settings", "Налаштування"),
    "group.controls": ("Controls", "Керування"),
    "group.safety": ("Safety", "Безпека"),
    "group.speed": ("Speed", "Швидкість"),
    "group.alerts": ("Notifications", "Сповіщення"),
    "group.app": ("App", "Програма"),
    "group.about": ("About", "Про програму"),
    "set.start_key": ("Start hotkey", "Клавіша запуску"),
    "set.start_key.text": ("Starts at the current mouse position", "Запускає з поточної позиції миші"),
    "set.stop_key": ("Stop hotkey", "Клавіша зупинки"),
    "set.stop_key.text": ("Stops right away", "Зупиняє одразу"),
    "set.keys_same": ("Start and stop need different keys.", "Для запуску й зупинки потрібні різні клавіші."),
    "set.key_taken": (
        "{key} is already used by another program. Pick a different key.",
        "Клавіша {key} уже зайнята іншою програмою. Виберіть іншу.",
    ),
    "set.focus": ("Only click inside Arma Reforger", "Клікати лише у вікні Arma Reforger"),
    "set.focus.text": ("Pauses while another window is in front", "Пауза, поки попереду інше вікно"),
    "set.mouse": ("Stop when I move the mouse", "Зупиняти, коли я рухаю мишею"),
    "set.mouse.text": ("Grab the mouse to take back control", "Візьміться за мишу, щоб повернути керування"),
    "set.fast": ("Fast close", "Швидке закриття"),
    "set.fast.text": (
        "Click the ESC button on screen instead of pressing the key",
        "Натискати кнопку ESC на екрані замість клавіші",
    ),
    "set.timing": ("Timing", "Затримки"),
    "set.timing.text": (
        "How long each step waits. The defaults suit most servers.",
        "Скільки чекає кожен крок. Стандартні значення підходять більшості серверів.",
    ),
    "set.wait_after_click": ("Wait after clicking Join", "Пауза після натискання Join"),
    "set.connect_timeout": ("Try again if nothing happens after", "Нова спроба, якщо нічого не сталося за"),
    "set.pause_before_retry": ("Pause between attempts", "Пауза між спробами"),
    "set.escape_hold": ("Hold the ESC key for", "Утримувати ESC"),
    "unit.seconds": (" s", " с"),
    "set.notify_queue": ("When I get into the queue", "Коли я потрапляю в чергу"),
    "set.notify_queue.text": ("As soon as the queue screen shows", "Щойно з'являється екран черги"),
    "set.notify_game": ("When I'm in the game", "Коли я вже в грі"),
    "set.notify_game.text": (
        "Reads the game's own log to see when the queue lets you in",
        "Читає журнал самої гри, щоб побачити, коли черга вас пропустила",
    ),
    "set.sound": ("Play a sound", "Звуковий сигнал"),
    "set.sound.text": ("Three short beeps", "Три короткі сигнали"),
    "set.phone": ("Notify my phone", "Сповіщення на телефон"),
    "set.phone.text": (
        "Free push through the ntfy app, no account needed",
        "Безкоштовно через застосунок ntfy, без реєстрації",
    ),
    "set.phone.placeholder": ("Topic name", "Назва теми"),
    "set.phone.help": (
        "Install ntfy on your phone and subscribe to this topic. Anyone who knows the name "
        "can read it, so keep it hard to guess.",
        "Встановіть ntfy на телефон і підпишіться на цю тему. Повідомлення може прочитати "
        "будь-хто, хто знає назву, тож зробіть її складною.",
    ),
    "set.discord": ("Post to Discord", "Повідомлення в Discord"),
    "set.discord.text": (
        "Send a message to a channel through a webhook",
        "Надсилати повідомлення в канал через вебхук",
    ),
    "set.discord.help": (
        "In Discord: channel settings › Integrations › Webhooks › New webhook › Copy webhook URL.",
        "У Discord: налаштування каналу › Інтеграції › Вебхуки › Новий вебхук › Копіювати URL вебхука.",
    ),
    "set.discord.invalid": (
        "This isn't a Discord webhook link. It starts with https://discord.com/api/webhooks/",
        "Це не посилання на вебхук Discord. Воно починається з https://discord.com/api/webhooks/",
    ),
    "button.send_test": ("Send test", "Надіслати тест"),
    "button.sending": ("Sending…", "Надсилання…"),
    "test.ntfy.ok": (
        "Sent. If nothing arrives, check that your phone uses the same topic.",
        "Надіслано. Якщо нічого не прийшло, перевірте, що на телефоні та сама тема.",
    ),
    "test.discord.ok": ("Sent. Check the channel.", "Надіслано. Перевірте канал."),
    "test.failed": (
        "Couldn't send: {error}. Check your internet connection and try again.",
        "Не вдалося надіслати: {error}. Перевірте інтернет і спробуйте ще раз.",
    ),
    "set.top": ("Keep on top", "Поверх інших вікон"),
    "set.top.text": ("Stay above other windows", "Вікно завжди зверху"),
    "set.tray": ("Close to the tray", "Згортати в трей"),
    "set.tray.text": (
        "Keeps running in the notification area when you close the window",
        "Після закриття вікна програма працює в області сповіщень",
    ),
    "set.updates": ("Check for updates", "Перевіряти оновлення"),
    "set.updates.text": (
        "Asks GitHub for a newer version at startup. Nothing else is sent.",
        "Під час запуску перевіряє на GitHub, чи є нова версія. Більше нічого не надсилається.",
    ),
    "set.language": ("Language", "Мова"),
    "set.language.text": ("Changes right away", "Змінюється одразу"),
    "set.diagnostics": ("Diagnostics", "Діагностика"),
    "set.diagnostics.text": (
        "See what the app sees and find the log files",
        "Що бачить програма, і файли журналу",
    ),
    "set.about.text": (
        "Version {version} · by lime98 · MIT licence",
        "Версія {version} · автор lime98 · ліцензія MIT",
    ),
    "button.source": ("Source code", "Вихідний код"),
    # Diagnostics
    "diag.title": ("Diagnostics", "Діагностика"),
    "diag.intro": (
        "Live readings from the screen under your mouse. Open the game's server full dialog "
        "or the queue screen to see the values change.",
        "Показники з екрана, на якому зараз миша. Відкрийте в грі вікно заповненого сервера "
        "або екран черги, і значення зміняться.",
    ),
    "diag.window": ("Active window", "Активне вікно"),
    "diag.window.arma": ("Arma Reforger detected", "Arma Reforger знайдено"),
    "diag.window.other": ("Not Arma Reforger", "Не Arma Reforger"),
    "diag.display": ("Display", "Екран"),
    "diag.red": ("Server full colour", "Колір заповненого сервера"),
    "diag.yellow": ("Queue text colour", "Колір тексту черги"),
    "diag.share": ("{value} of the area, needs over {limit}", "{value} області, потрібно понад {limit}"),
    "diag.esc": ("ESC button", "Кнопка ESC"),
    "diag.esc.found": ("Found at {x}, {y}", "Знайдено: {x}, {y}"),
    "diag.esc.none": ("Not visible", "Не видно"),
    "diag.preview": ("Scanned area", "Область сканування"),
    "diag.verdict.full": ("Reads as: server full", "Розпізнано: сервер заповнений"),
    "diag.verdict.queue": ("Reads as: queue screen", "Розпізнано: екран черги"),
    "diag.verdict.none": ("Reads as: nothing to react to", "Розпізнано: нічого, на що треба реагувати"),
    "diag.unavailable": ("Couldn't read the screen: {error}", "Не вдалося прочитати екран: {error}"),
    "diag.copy": ("Copy report", "Копіювати звіт"),
    "diag.copied": ("Copied", "Скопійовано"),
    "diag.logs": ("Open log folder", "Відкрити теку журналу"),
    "diag.logs.text": (
        "Attach the newest aqj.log when you report a bug.",
        "Додайте найновіший aqj.log, коли повідомляєте про помилку.",
    ),
    # Crash, tray, push
    "crash.title": ("Something went wrong", "Щось пішло не так"),
    "crash.text": (
        "{error}\n\nThe details are saved in the log. If this keeps happening, report it on GitHub "
        "and attach the newest aqj.log.",
        "{error}\n\nПодробиці збережено в журналі. Якщо це повторюється, повідомте на GitHub "
        "і додайте найновіший aqj.log.",
    ),
    "tray.open": ("Open", "Відкрити"),
    "tray.stop": ("Stop", "Зупинити"),
    "tray.quit": ("Quit", "Вийти"),
    "tray.still_running": (
        "Still running in the notification area.",
        "Програма працює далі в області сповіщень.",
    ),
    "push.title": ("You're in the queue", "Ви в черзі"),
    "push.text": (
        "Arma Reforger: got in after {attempts}, waited {time}.",
        "Arma Reforger: ви в черзі. Спроб: {n}, час: {time}.",
    ),
    "push.in_game.title": ("You're in the game", "Ви в грі"),
    "push.in_game.text": ("Arma Reforger: you're on {server}.", "Arma Reforger: ви на сервері {server}."),
    "push.queue_lost.title": ("Dropped out of the queue", "Вас викинуло з черги"),
    "push.queue_lost.text": (
        "Arma Reforger: the server removed you from the queue.",
        "Arma Reforger: сервер прибрав вас із черги.",
    ),
    "log.watch_start": ("Watching the game log: {path}", "Стежу за журналом гри: {path}"),
    "log.watch_missing": (
        "Game log not found, so the in-game alert is off",
        "Журнал гри не знайдено, тож сповіщення про вхід у гру вимкнено",
    ),
    "log.joining": ("Queue passed, joining {server}", "Черга пройдена, вхід на {server}"),
    "log.in_game": ("In the game on {server}", "У грі на {server}"),
    "log.dropped": ("Dropped out of the queue", "Викинуло з черги"),
    "log.watch_timeout": (
        "Stopped watching the game log after 3 hours",
        "Припинено стежити за журналом гри через 3 години",
    ),
    "unknown_server": ("the server", "сервер"),
    "diag.gamelog": ("Game log", "Журнал гри"),
    "diag.gamelog.none": (
        "Not found. The in-game alert needs it.",
        "Не знайдено. Він потрібен для сповіщення про вхід у гру.",
    ),
    "push.test": (
        "Test notification. You'll get one like this when you're in the queue.",
        "Тестове сповіщення. Таке саме прийде, коли ви будете в черзі.",
    ),
}

_current = "en"


def system_language() -> str:
    """Ukrainian on a Ukrainian Windows, English everywhere else."""
    try:
        langid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
    except (AttributeError, OSError):
        return "en"
    return "uk" if langid & 0x3FF == 0x22 else "en"  # LANG_UKRAINIAN


def set_language(setting: str) -> str:
    """Apply 'en' or 'uk'; anything else means English. Returns the language used."""
    global _current
    _current = setting if setting in ("en", "uk") else "en"
    return _current


def language() -> str:
    return _current


def attempts(n: int) -> str:
    if _current == "uk":
        if n % 10 == 1 and n % 100 != 11:
            word = "спроба"
        elif n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
            word = "спроби"
        else:
            word = "спроб"
        return f"{n} {word}"
    return f"{n} attempt" + ("" if n == 1 else "s")


def tr(key: str, /, **params: object) -> str:
    en, uk = STRINGS[key]
    text = uk if _current == "uk" else en
    if "n" in params and "attempts" not in params:
        params["attempts"] = attempts(int(params["n"]))  # type: ignore[arg-type]
    return text.format(**params) if params else text
