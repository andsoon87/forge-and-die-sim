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
| `data.py` | Игровые данные: классы, стартовое снаряжение (`STARTING_EQUIPMENT`), предметы (`EQUIPMENT`), 
таблица качества (`EQUIPMENT_QUALITY_TABLE`), монстры, тайлы, действия, таблицы лагерей, 20 карт событий. 
**Только читается** |
| `simulator.py` | Движок: ходьба, бой, найм, события, сокровищницы, торговец, level-up, `free_phase` (вкл. 
`solver.drink`), побег, запись лога партии; `make_fighter_copy` |
| `combat.py` | Бой: `run_combat` (раунды, инициатива, атаки, награда); работает с копиями, возвращает дельты |
| `run_player.py` | Tkinter-обозреватель прогона: таблица партий, сводка, гистограммы, TSV |
| `game_player.py` | Tkinter-плеер одной партии: карта этажей, таблица шагов, свойства, график |
| `combat_player.py` | Tkinter-плеер одного боя: бойцы / раунды / противники, действия раунда |
| `equipment.py` | Снаряжение и эликсиры: `get_equipment`/`get_slot`/`get_quality`/`is_elixir`, `recalc_stats`, 
`grant_item`, `collect_trash`, `trim_inventories`, `resolve_trade`, `resolve_treasure`, `_roll_quality` |
| `solvers.py` | `Solver`-интерфейс, `make_solver(kind, profile)`, заглушки `Human`/`NN` |
| `bots.py` | `BotSolver` + `bot_move`/`bot_decide`/`bot_distribute`/`bot_trade`/`bot_drink` |

Запуск плееров: `run_player` → `game_player` (двойной клик по партии) → `combat_player` (кнопка «Открыть бой»).

## Архитектура и соглашения

**Версионирование.** Версия одна — `PROJECT_VERSION` в `config.py`. «Forge & Die II» — название игры. Версия 
правил отдельно не ведётся.

**Индексация.** Везде 0-индексация: данные, логи, код. `+1` — только в UI при показе (этажи, позиции, id 
монстров).

**`data.py` только читается.** Никакая мутация данных игры в `data.py` недопустима. Изменяемое состояние живёт
 в копиях:
- тайлы этажа — в `floor_state["tiles"]` (копии из `data.TILES`);
- бойцы — в `party`;
- противники — в боевых экземплярах (`draw_monsters` / `build_camp_monsters`).

**Решатели (`Solver`).** Движок не знает, кто принимает решения: `play_one_game` получает готовый `solver` и 
зовёт `solver.move/decide/distribute/trade`. `make_solver(kind, profile)` — фабрика: `bot` → `BotSolver` 
(стили `rusher`/...), `human`/`nn` — заглушки (после 8.0). CLI: `--solver bot|human|nn`, `--profile ...`.

**Логи — для плееров, не для чтения глазами.** В логах коды/ссылки (`tile_id`, `source` = `{type, pool, monster}` 
/ `{type, class, level}`, `action` как int). Имена восстанавливаются из `data.py`. `combat_log` самодостаточен: 
не требует соседних шагов (в нём `party` на начало боя, `monsters`, `rounds` с `hp_start_round`/`initiative`/
`actions`, финальный раунд-снимок, `result`, `xp_gained`/`gold_gained`).

**`party` в шаге — после хода.** Трупы (`hp=0`) живут в `party` до начала следующего хода: чистка — в `free_phase` 
(`cleanup_dead`). «До боя» — из `combat_log["party"]` и `hp_start_round`; «до шага» — из предыдущего шага.

**Снаряжение.** `data.EQUIPMENT` — список предметов; ссылка на предмет везде — строка `code` (`"UW01"`), имя 
резолвится из `data.py` по коду. У бойца: `inventory` (список кодов в порядке получения), `equipped_weapon`/
`equipped_armor` (код или `None`). Бонусы дают только экипированные W/S и все аксессуары (`slot == "A"`) из 
`inventory`. `at`/`df`/`max_hp` — кэш в бойце, пересчитывается `recalc_stats` (база класса + снаряжение); триггеры 
— `create_boiets`, `free_phase` (после `check_level_up`). `check_level_up` лечит на чистую классовую дельту 
(`base_hp[new] − base_hp[old]`), клэмп `hp` — в `recalc_stats`.

**Эликсиры (5.3).** Слот `"E"` (`UE01`/`RE01`/`VE01`/`LE01` — лечение, `RE02` — скорость-заглушка). 1 эликсир
 = 1 слот инвентаря. Эффект применяется немедленно при выпивании; выпивается только вне боя (`solver.drink` в
 `free_phase`, не более 1 на бойца за ход). В колоды снаряжения **не попадают** (пропускаются при построении
 `equipment_decks`, сокровищница их не выдаёт); выдаются только торговцем (ассортимент по этажу — 
`data.ELIXIR_QUALITY_BY_FLOOR`). Выбывшие эликсиры исчезают (`collect_trash` их пропускает). `RE02` — заглушка: 
`bonus: {}`, `price: 0`, эффект инициативы в 5.3 не реализован (перенесён в 6.1).

**Колоды снаряжения.** В начале партии создаются 4 колоды по качеству (`U`/`R`/`V`/`L`) из `data.EQUIPMENT`, 
каждая перемешана. Эликсиры (slot `"E"`) в колоды **не попадают** — пропускаются при построении. Выдача в
сокровищнице тянет из колоды нужного качества (`EQUIPMENT_QUALITY_TABLE`, §6.2); если колода пуста — компенсация
золотом (§6.2). Выбывшие предметы (смерть, обрезка, остаток раздачи) собираются в `trash` в `free_phase` и
возвращаются в колоды через `collect_trash` (вставка в случайное место, без перемешивания).

**Цены снаряжения.** `price` в `data.EQUIPMENT` взяты из RULES.md §10 и на этапе 5.1 используются только для 
выбора бота (`rusher` экипирует самое дорогое W/S) и отсева «мусора» (`price: 0`). Абсолютные значения в §10
прикидочные и не коррелируют строго с ценностью предмета — пересмотр цен
запланирован на этап балансировки (монте-карло), после завершения механик.
У предметов со «сложными свойствами» (пока не реализованы, 6.1) в `data.py`
стоит `price: 0` — это осознанно, чтобы бот их не продавал; цены из §10
вернутся вместе с реализацией свойств. Цены эликсиров (2/6/13/40/6) —
актуальны.

**Бонусы и способности (6.0).** У классов, монстров и предметов — единый формат:
`bonus` (числовые модификаторы: `hp`, `at`, `df`, `init`, …) и `ability` (список кортежей `(id, *params)` — то, 
что даёт выбор действия). Способности описаны в `data.ABILITIES` (`{"name", "params", "rules"}`; `rules` — 
заглушка до 6.3+). Инициатива (`init`) — бонус: `recalc_stats` = база класса + снаряжение; эликсир RE02 даёт 
временный `init` через `floor_state["active_effects"]` (эффект «до конца ближайшего следующего боя»: `make_fighter_copy` 
при входе в бой добавляет `init` к копии и уменьшает `turns_left`; `tick_active_effects` такие эффекты пропускает). 
`run_combat` получает боевые копии (`make_fighter_copy`), оригиналы `party` не мутируются; возвращает `(combat_log, changes)` 
с дельтами `hp_delta`/`xp_delta`/`gold_delta`, `play_one_game` применяет их к `party`.

**`resolve_tile` предлагает, `bot_*` решают.** `resolve_tile(position, floor_state, party) -> list[Action]` — 
только варианты. `bot_move` — направление, `bot_decide` — выбор `Action`. Не смешивать.

**События.** 20 карт в `data.EVENTS`, колода на этаж (`floor_state["events_deck"]`, без повторов). `resolve_tile` 
тянет карту в `tile["event"]`, проигрывает правила (`play_event_rules`, d6 — здесь), фиксирует результат в 
`tile["event_result"]` и собирает монстров в `tile["monsters"]`. Применение — в `play_one_game` через `apply_event` 
(детерминированно, без повторных бросков). Правило события: `{"select", "condition", "effects"}`. `select` — 
`{"all": True}` / `{"random": True}` / `{"max": field}`; `condition` — дерево (`{op: (left, right)}`, 
`{"d6": (lo, hi)}`, `{"and"/"or"/"not": ...}`); `effects` — объект (`gold`/`hp`/`xp`/`turns`/`monster`/`guide`). 
Длительные эффекты (`turns`) — в `floor_state["active_effects"]`, привязаны к бойцу (`target`), тикают в `free_phase` 
(до `cleanup_dead`). Бой из события — через `monster`-эффект (`(pool, index)`; монстры собираются в `resolve_tile`, 
бой — `Action.FIGHT`).

**Сокровищница, найм, торговец (5.3).** Мимик (d6=1 в сокровищнице) --
бой: `resolve_tile` собирает `tile["monsters"]` через `build_mimic`, `Action.FIGHT`.
Найм в лагере: стартовый предмет класса выдаётся через `grant_item`; если
карточки уже нет в колоде -- боец нанимается без предмета, + `price` золотом.
Торговец: `Action.TRADE` (доступен всегда). `bot_trade(party, floor_state)`
возвращает список сделок `(boiets_idx, code)`: сначала продажи (неэкипированные
W/S с `price > 0`), затем покупки эликсиров (по `code[1]=="E"`). Для каждого
бойца по очереди: sell → buy «на сейчас» (лечение, если есть дефицит `hp`;
отсев по оверхилу ≤25%; покрывающий → самый дешёвый; иначе самый большой heal;
один, даже при полном инвентаре) → buy «про запас» (до свободных слотов после
sell, от сильных к слабым, с учётом этажа и золота). `resolve_trade` идёт
строго по списку, при нехватке золота — `trade_no_gold`, при отсутствии
предмета — `trade_miss`. Эликсиры не продаются; обратный выкуп снаряжения
невозможен.

**Последовательность хода:**
1. `free_phase` — тик `active_effects`; `solver.drink` (эликсиры, ≤1 на бойца); `solver.distribute` (перераспределение
снаряжения и золота, трупы — источник); `trim_inventories` (обрезка до 6); чистка трупов; level-up; `recalc_stats`;
`collect_trash` (возврат выбывших предметов в колоды; эликсиры исчезают). Если команда вымерла — `dead`.
2. `bot_move` — 1 / -1.
3. `resolve_tile` — тянет тайл при необходимости; для лагеря делает 3 броска и пишет в `tile["camp"]`.
4. Смена позиции, `floor_steps += 1`.
5. Монстры собраны в `resolve_tile` (в `tile["monsters"]`); бой — через    `Action.FIGHT`. Перед боем — `make_fighter_copy` 
   (боевые копии бойцов с учётом `active_effects`), затем `run_combat(party_copy, monsters)`.
6. `bot_decide` (если вариантов > 1).
7. Обработка `Action` (`HIRE` / `FIGHT` / `FLEE` / `FORGE` / `SKIP`).
8. Запись шага в лог.
9. Переход на этаж (`FORGE`), `MAX_FLOOR_STEPS`.

**`run_combat(party, monsters)`** (в `combat.py`) — без `kind`. `party` — **боевые копии** (`make_fighter_copy`), `monsters` — боевые экземпляры с полем `source` (`{"type": "monster", ...}` / `{"type": "camp", ...}`), по нему плееры различают тип. Возвращает `(combat_log, changes)`: `changes` — дельты `hp_delta`/`xp_delta`/`gold_delta` по порядку `party` (оригиналы не трогаются). Награда — `sum(m["xp"])`, `sum(m["gd"])`, делёж между выжившими. Чистка трупов — не здесь, а в `free_phase`.

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

