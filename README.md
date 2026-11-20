# Forge & Die II — Simulator

Тестовый проект создаваемый для развлечения 

Симулятор настольной игры **Forge & Die II** (rogue-like, 1 игрок).
Прогоняет тысячи партий по заданным правилам, собирает статистику
(смертность по этажам, скорость прокачки, экономика) и помогает
балансировать игру.

## Правила

Полные правила: [RULES.md](RULES.md).

Правила — это «источник истины». Симулятор реализует их; числа
(HP, AT, DF, пороги XP, награды, цены) хранятся в `data.py`
и соответствуют таблицам из `RULES.md`.

## Структура проекта

| Файл | Назначение |
|------|------------|
| `RULES.md` | Правила игры (источник истины) |
| `config.py` | Константы проекта (`PROJECT_VERSION`, лимиты, пути, дефолты) |
| `data.py` | Игровые данные: классы, стартовое снаряжение (`STARTING_EQUIPMENT`), предметы (`EQUIPMENT`), таблица качества (`EQUIPMENT_QUALITY_TABLE`), монстры, тайлы, действия, таблицы лагерей, 20 карт событий. **Только читается** |
| `simulator.py` | Движок: ходьба, бой, найм, события, сокровищницы, level-up, снаряжение (`recalc_stats`, `bot_distribute`), побег, запись лога партии |
| `run_player.py` | Tkinter-обозреватель прогона: таблица партий, сводка, гистограммы, TSV |
| `game_player.py` | Tkinter-плеер одной партии: карта этажей, таблица шагов, свойства, график |
| `combat_player.py` | Tkinter-плеер одного боя: бойцы / раунды / противники, действия раунда |
| `equipment.py` | Снаряжение: `get_equipment`, `recalc_stats` (в 5.3 — полный) |
| `solvers.py` | `Solver`-интерфейс, `make_solver(kind, profile)`, заглушки `Human`/`NN` |
| `bots.py` | `BotSolver` + `bot_move`/`bot_decide`/`bot_distribute`/`bot_trade` |

Запуск плееров: `run_player` → `game_player` (двойной клик по партии) → `combat_player` (кнопка «Открыть бой»).

## Архитектура и соглашения

**Версионирование.** Версия одна — `PROJECT_VERSION` в `config.py`. «Forge & Die II» — название игры. Версия правил отдельно не ведётся.

**Индексация.** Везде 0-индексация: данные, логи, код. `+1` — только в UI при показе (этажи, позиции, id монстров).

**`data.py` только читается.** Никакая мутация данных игры в `data.py` недопустима. Изменяемое состояние живёт в копиях:
- тайлы этажа — в `floor_state["tiles"]` (копии из `data.TILES`);
- бойцы — в `party`;
- противники — в боевых экземплярах (`draw_monsters` / `build_camp_monsters`).

**Решатели (`Solver`).** Движок не знает, кто принимает решения: `play_one_game` получает готовый `solver` и зовёт `solver.move/decide/distribute/trade`. `make_solver(kind, profile)` — фабрика: `bot` → `BotSolver` (стили `rusher`/...), `human`/`nn` — заглушки (после 8.0). CLI: `--solver bot|human|nn`, `--profile ...`.

**Логи — для плееров, не для чтения глазами.** В логах коды/ссылки (`tile_id`, `source` = `{type, pool, monster}` / `{type, class, level}`, `action` как int). Имена восстанавливаются из `data.py`. `combat_log` самодостаточен: не требует соседних шагов (в нём `party` на начало боя, `monsters`, `rounds` с `hp_start_round`/`initiative`/`actions`, финальный раунд-снимок, `result`, `xp_gained`/`gold_gained`).

**`party` в шаге — после хода.** Трупы (`hp=0`) живут в `party` до начала следующего хода: чистка — в `free_phase` (`cleanup_dead`). «До боя» — из `combat_log["party"]` и `hp_start_round`; «до шага» — из предыдущего шага.

**Снаряжение.** `data.EQUIPMENT` — список предметов; ссылка на предмет везде — строка `code` (`"UW01"`), имя резолвится из `data.py` по коду. У бойца: `inventory` (список кодов в порядке получения), `equipped_weapon`/`equipped_armor` (код или `None`). Бонусы дают только экипированные W/S и все аксессуары (`slot == "A"`) из `inventory`. `at`/`df`/`max_hp` — кэш в бойце, пересчитывается `recalc_stats` (база класса + снаряжение); триггеры — `create_boiets`, `free_phase` (после `check_level_up`). `check_level_up` лечит на чистую классовую дельту (`base_hp[new] − base_hp[old]`), клэмп `hp` — в `recalc_stats`.

**Колоды снаряжения.** В начале партии создаются 4 колоды по качеству
(`U`/`R`/`V`/`L`) из `data.EQUIPMENT`, каждая перемешана. Выдача в
сокровищнице тянет из колоды нужного качества (`EQUIPMENT_QUALITY_TABLE`,
§6.2); если колода пуста — компенсация золотом (§6.2). Выбывшие предметы
(смерть, обрезка, остаток раздачи) собираются в `trash` в `free_phase` и
возвращаются в колоды через `collect_trash` (вставка в случайное место,
без перемешивания).

**Цены снаряжения.** `price` в `data.EQUIPMENT` взяты из RULES.md §10 и на
этапе 5.1 используются только для выбора бота (`rusher` экипирует самое
дорогое W/S) и отсева «мусора» (`price: 0`). Абсолютные значения в §10
прикидочные и не коррелируют строго с ценностью предмета — пересмотр цен
запланирован на этап балансировки (монте-карло), после завершения механик.

**`resolve_tile` предлагает, `bot_*` решают.** `resolve_tile(position, floor_state, party) -> list[Action]` — только варианты. `bot_move` — направление, `bot_decide` — выбор `Action`. Не смешивать.

**События.** 20 карт в `data.EVENTS`, колода на этаж (`floor_state["events_deck"]`, без повторов). `resolve_tile` тянет карту в `tile["event"]`, проигрывает правила (`play_event_rules`, d6 — здесь), фиксирует результат в `tile["event_result"]` и собирает монстров в `tile["monsters"]`. Применение — в `play_one_game` через `apply_event` (детерминированно, без повторных бросков). Правило события: `{"select", "condition", "effects"}`. `select` — `{"all": True}` / `{"random": True}` / `{"max": field}`; `condition` — дерево (`{op: (left, right)}`, `{"d6": (lo, hi)}`, `{"and"/"or"/"not": ...}`); `effects` — объект (`gold`/`hp`/`xp`/`turns`/`monster`/`guide`). Длительные эффекты (`turns`) — в `floor_state["active_effects"]`, привязаны к бойцу (`target`), тикают в `free_phase` (до `cleanup_dead`). Бой из события — через `monster`-эффект (`(pool, index)`; монстры собираются в `resolve_tile`, бой — `Action.FIGHT`).

**Сокровищница, найм, торговец (5.2).** Мимик (d6=1 в сокровищнице) --
бой: `resolve_tile` собирает `tile["monsters"]` через `build_mimic`, `Action.FIGHT`.
Найм в лагере: стартовый предмет класса выдаётся через `grant_item`; если
карточки уже нет в колоде -- боец нанимается без предмета, + `price` золотом.
Торговец: `Action.TRADE` (доступен всегда), `bot_trade` выбирает неэкипированные
W/S с `price > 0`, `resolve_trade` продаёт (удаляет предмет, начисляет `price`
тому бойцу). Эликсиры (покупка) -- 5.3.

**Последовательность хода:**
1. `free_phase` — тик `active_effects`; `solver.distribute` (перераспределение снаряжения и золота, трупы — источник); `trim_inventories` (обрезка до 6); чистка трупов; level-up; `recalc_stats`; `collect_trash` (возврат выбывших предметов в колоды). Если команда вымерла — `dead`.
2. `bot_move` — 1 / -1.
3. `resolve_tile` — тянет тайл при необходимости; для лагеря делает 3 броска и пишет в `tile["camp"]`.
4. Смена позиции, `floor_steps += 1`.
5. Монстры собраны в `resolve_tile` (в `tile["monsters"]`); бой — через `Action.FIGHT`.
6. `bot_decide` (если вариантов > 1).
7. Обработка `Action` (`HIRE` / `FIGHT` / `FLEE` / `FORGE` / `SKIP`).
8. Запись шага в лог.
9. Переход на этаж (`FORGE`), `MAX_FLOOR_STEPS`.

**`run_combat(party, monsters)`** — без `kind`. Противники — список боевых экземпляров с полем `source` (`{"type": "monster", ...}` / `{"type": "camp", ...}`), по нему плееры различают тип. Награда — `sum(m["xp"])`, `sum(m["gd"])`, делёж между выжившими. Чистка трупов — не здесь, а в `free_phase`.

**Плееры** запускаются через `subprocess.Popen([sys.executable, <script>, ...])`, пути — через `os.path.dirname(os.path.abspath(__file__))`. Настройки — в `~/.config/forge-and-die-sim/<player>.json` (без дефолтов: нет файла — всё выключено).

**TSV** — таб, `utf-8-sig`; галочки управляют и графиком, и TSV.

## Запуск

```bash
# прогон N партий (seed для воспроизводимости)
# --solver bot|human|nn --profile rusher
python simulator.py --games 1000 --seed 1

# обозреватель прогона; кнопка «Новый…» — запуск simulator.py из интерфейса
python run_player.py

# обозреватель прогона (без аргумента — откроет last_run_dir, если есть)
python run_player.py

# плеер партии / боя — обычно из run_player / game_player
python game_player.py <log_path>
python combat_player.py <log_path> <step_index>

