"""Instructions given to the extraction model.

One template per tariff block, filled from config. Nothing country-specific is written
here: the city, the supplier, the currency and the units are substituted by the caller,
so adding a country never means editing this file.

Two rules matter more than the rest and are repeated in every template:

* take only the tariff a household pays — the same page usually prints an industrial one,
  a pre-VAT one and an economically justified one right next to it;
* return nothing rather than something. A model asked for a number will produce one from
  memory when the page does not have it, and that number is indistinguishable from a real
  extraction once it is in the file.
"""

from datetime import date

# Shape of one dated tariff version, per block. Kept next to the rules so the model sees
# the field names and the constraints on them in one place.
PERIOD_FIELDS = {
    "water": (
        '"water_supply": число — цена 1 {unit} холодной (питьевой) воды,\n'
        '      "sewage": число — цена 1 {unit} водоотведения,\n'
        '      "total_rate": число — сумма двух предыдущих полей, если она напечатана в документе; иначе null'
    ),
    "hot_water": (
        '"component_water": число — компонент на теплоноситель или холодную воду, за 1 {unit},\n'
        '      "component_energy": число — компонент на тепловую энергию, за 1 Гкал,\n'
        '      "heat_norm": число — норматив расхода тепловой энергии на подогрев 1 {unit},\n'
        '      "rate": число — цена 1 {unit} горячей воды, если она указана в документе готовой'
    ),
    "heating": (
        '"rate_gcal": число — цена 1 Гкал тепловой энергии,\n'
        '      "rate_gcal_hour": число — плата за подключённую нагрузку (Гкал/час) '
        'у двухставочного тарифа, иначе 0,\n'
        '      "rate_gcal_hour_in_thousands": true, если эта плата напечатана в тысячах рублей '
        '(«тыс. руб.»), иначе false,\n'
        '      "tariff_type": "one_rate" или "two_rate"'
    ),
}

# Asked only of a source config marks with `read_heat_norms`: the table is regional, few sources
# print it, and every field asked of a source that has no answer for it is one more chance for
# the model to fill something from the wrong table.
HEAT_NORMS_FIELD = (
    ',\n      "heat_norms": список всех нормативов подогрева по типам домов, если документ печатает '
    'такую таблицу, иначе null. Элемент: {{"system": "open" — открытая система, "closed" — '
    'закрытая, "decentralized" — нецентрализованная; "insulated_risers": true — с '
    'изолированными стояками, false — с неизолированными, null — не указано; "towel_rails": '
    'true — с полотенцесушителями, false — без, null — не указано; "value": норматив, '
    'Гкал на 1 {unit}}}. Строки таблицы без числа не включай'
)

# The unit as a page prints it, so the instruction reads the way the document does.
UNIT_NAMES = {"m3": "м³", "Gcal": "Гкал", "kWh": "кВт·ч"}


def unit_name(unit: str) -> str:
    return UNIT_NAMES.get(unit, unit)


BLOCK_NAMES = {
    "water": "холодное водоснабжение и водоотведение",
    "hot_water": "горячее водоснабжение",
    "heating": "отопление (тепловая энергия)",
}

CITY_TEMPLATE = """Извлеки из приведённого документа действующий коммунальный тариф.

Сегодня {today}.
Услуга: {block_name}.
Населённый пункт: {city_name}.
{supplier_line}Валюта: {currency}.
{hint_line}

Верни СТРОГО такой JSON и ничего кроме него:
{{
  "supplier": "название организации, как оно напечатано в документе",
  "periods": [
    {{
      "from": "YYYY-MM-DD",
      "to": "YYYY-MM-DD или null, если период бессрочный",
      {fields},
      "decree_info": "реквизиты документа, которым установлен тариф, как напечатано"
    }}
  ]
}}

Правила, обязательные к соблюдению:

1. Бери ТОЛЬКО тариф для населения (для граждан, для бытовых потребителей) и ТОЛЬКО
   с учётом НДС. Если в таблице есть колонки «без НДС» и «для населения (с НДС)» —
   нужна вторая. Тарифы для прочих потребителей, экономически обоснованные и льготные
   для отдельных категорий граждан игнорируй.
2. Верни периоды, действующие сегодня и в будущем. Регуляторы публикуют график
   индексации на годы вперёд — эти будущие периоды нужны. Периоды, закончившиеся
   до сегодняшнего дня, не возвращай вообще: они уже не применяются.
3. Даты периодов приводи к формату YYYY-MM-DD.
4. Числа возвращай числами, десятичный разделитель — точка. Не округляй.
5. Ничего не вычисляй самостоятельно: возвращай числа ровно так, как они напечатаны.
   {no_math}
6. Если в документе нет тарифа для указанного населённого пункта или услуги —
   верни {{"supplier": "", "periods": []}}. Пустой ответ является правильным ответом.
7. НИКОГДА не заполняй поле по памяти, по аналогии с другим городом или по своим
   представлениям о том, каким тариф должен быть. Данных нет в документе — значит их нет.
8. Каждый период должен встретиться в ответе ровно один раз. Если документ даёт для одного
   периода несколько тарифов — для разных зон, адресов, групп потребителей или систем
   теплоснабжения, — верни только тот, который назван в уточнении. Если уточнения нет или по
   нему выбрать нельзя — верни {{"supplier": "", "periods": []}}: угаданный выбор хуже пустого
   ответа.
"""

NO_MATH = {
    "water": "В частности, не складывай водоснабжение с водоотведением сам: если сумма "
             "напечатана — бери напечатанную, если не напечатана — верни null, "
             "сумму посчитает программа.",
    "hot_water": "В частности, если тариф двухкомпонентный, верни оба компонента и норматив "
                 "подогрева по отдельности и НЕ перемножай их. Норматив ищи в этом же "
                 "документе или в приведённых рядом; если норматива нет — оставь heat_norm "
                 "пустым, а поле rate заполняй только если готовая цена за 1 {unit} "
                 "напечатана в документе.",
    "heating": "В частности, не пересчитывай тариф из цены без НДС — бери напечатанный "
               "с НДС.",
}

ELECTRICITY_TEMPLATE = """Извлеки из приведённого документа действующие тарифы на
электроэнергию для населения — все цены, которые документ печатает для перечисленных ниже групп.

Сегодня {today}.
Регион: {region}.
{supplier_line}Валюта: {currency}. Единица: {unit}.
{hint_line}
Группы потребителей, которые нужны (код — описание):
{plans}

Верни СТРОГО такой JSON и ничего кроме него:
{{
  "periods": [
    {{
      "from": "YYYY-MM-DD",
      "to": "YYYY-MM-DD или null, если период бессрочный",
      "prices_in_subunits": true ТОЛЬКО если единица цены прямо названа в документе сотой долей валюты — копейки, тетри, бани, гяпики (qəpik), дирамы, тыйыны; драмы, сумы, тенге, рубли, сомы, сомони, лари, леи, манаты и гривны — основные единицы, для них false,
      "decree_info": "реквизиты документа, которым установлены тарифы, как напечатано",
      "plans": [
        {{
          "plan": "код группы из списка выше",
          "tier_basis": "part", если в тексте документа есть прямые слова о том, что цена ступени применяется к ЧАСТИ месячного потребления в пределах ступени; "whole", если есть прямые слова о том, что по цене ступени оплачивается ВСЁ потребление месяца; во всех остальных случаях null — не выводи это из границ ступеней и не угадывай,
          "tiers_per_resident": true, если документ прямо говорит, что границы ступеней установлены на одного проживающего человека; false, если прямо говорит, что на квартиру или лицевой счёт; иначе null,
          "monthly_charge": число — фиксированная ежемесячная плата для этой группы в основных единицах валюты, как напечатана, если напечатана; иначе null,
          "rates": [
            {{
              "meter": "single" — однотарифный (одноставочный, круглосуточный) счётчик, "two_zone" — по двум зонам суток, "three_zone" — по трём зонам,
              "zone": для single — "all"; для two_zone — "day" или "night"; для three_zone — "peak", "half_peak" или "night",
              "hours": "часы зоны, как напечатаны, в виде HH:MM - HH:MM; несколько интервалов через запятую; пустая строка, если для этой зоны часы не напечатаны — не вычисляй их из часов других зон",
              "tier": номер ступени месячного потребления по порядку, начиная с 1 («1 уровень», «минимальный тариф» — 1); null, если цена не зависит от объёма потребления,
              "above_kwh": число — нижняя граница ступени месячного потребления: цена действует для потребления СВЫШЕ этого числа; null, если ступень начинается с нуля или ступеней нет,
              "up_to_kwh": число — верхняя граница ступени включительно; null, если ступень не ограничена сверху или ступеней нет,
              "season_from": "MM-DD" — начало сезона, если цена действует каждый год в одни и те же месяцы («с 1 октября по 30 апреля»); иначе null. Цены, действующие до или после конкретной даты («по 31 мая включительно», «с 1 июня»), — это разные периоды, а не сезон,
              "season_to": "MM-DD" — конец сезона включительно; иначе null,
              "rate": число — цена 1 {unit}
            }}
          ]
        }}
      ]
    }}
  ]
}}

Правила, обязательные к соблюдению:

1. Бери ТОЛЬКО группы из списка выше. Каждой цене документа, относящейся к группе, — одна
   строка rates. Группу, для которой в документе нет цен, не возвращай.
2. Цены — ТОЛЬКО с учётом НДС, если документ печатает оба варианта. Если документ печатает
   только цены без НДС, верни их как есть.
3. Верни периоды, действующие сегодня и в будущем. Периоды, закончившиеся до сегодняшнего
   дня, не возвращай.
4. Числа возвращай числами, десятичный разделитель — точка. Ничего не вычисляй и не
   пересчитывай: ни зоны из коэффициентов, ни рубли из копеек, ни цены с НДС из цен без НДС.
5. Все группы одного периода делят его даты. Если цены разных групп меняются в разные даты,
   раздели год на периоды по всем этим датам и в каждый период включи все группы, повторив
   неизменившиеся цены.
6. Ступени записывай так, как они напечатаны: «до 200 кВт·ч» — above_kwh null, up_to_kwh 200;
   «от 201 до 400 кВт·ч» — above_kwh 200, up_to_kwh 400; «свыше 400 кВт·ч» — above_kwh 400,
   up_to_kwh null. Если границы ступени не напечатаны, а напечатан только её номер или название,
   заполни tier, а above_kwh и up_to_kwh оставь null.
7. Коэффициент, напечатанный рядом с ценой, не является ценой. Если для зоны напечатан только
   коэффициент без цены — не возвращай эту строку.
8. НИКОГДА не заполняй поле по памяти или по аналогии. Данных нет в документе — значит их нет.
   Если в документе нет ни одной цены группы, отмеченной как основная, верни {{"periods": []}}.
"""

GAS_TEMPLATE = """Извлеки из приведённого документа действующие цены природного газа для населения —
все цены, которые документ печатает для перечисленных ниже планов.

Сегодня {today}.
Населённый пункт: {city_name}.
{supplier_line}Валюта: {currency}.
{hint_line}
Планы, которые нужны (код — описание):
{plans}

Верни СТРОГО такой JSON и ничего кроме него:
{{
  "periods": [
    {{
      "from": "YYYY-MM-DD",
      "to": "YYYY-MM-DD или null, если период бессрочный",
      "decree_info": "реквизиты документа, которым установлены цены, как напечатано",
      "price_per": "m3", если цены напечатаны за 1 м³ (куб. м); "thousand_m3", если за 1000 м³ (тыс. куб. м),{distribution_fields}
      "plans": [
        {{
          "plan": "код плана из списка выше",
          "tier_basis": "part", если документ прямо говорит, что цена ступени применяется к ЧАСТИ потребления в пределах ступени; "whole", если прямо говорит, что по цене ступени оплачивается ВСЁ потребление; во всех остальных случаях null — не выводи это из границ ступеней и не угадывай,
          "monthly_charge": число — фиксированная ежемесячная плата плана, как напечатана, если напечатана; иначе null,
          "rates": [
            {{
              "tier": номер ступени потребления по порядку, начиная с 1; null, если цена не зависит от объёма,
              "above_m3": число — цена действует для потребления СВЫШЕ этого объёма; null, если ступень начинается с нуля или ступеней нет,
              "up_to_m3": число — верхняя граница ступени включительно; null, если ступень не ограничена сверху или ступеней нет,
              "tier_period": "month", если границы ступеней заданы на месяц; "year", если на год; null, если ступеней нет,
              "season_from": "MM-DD" — начало сезона, если цена действует каждый год в одни и те же месяцы; иначе null,
              "season_to": "MM-DD" — конец сезона включительно; иначе null,
              "rate": число — цена в единицах из price_per
            }}
          ]
        }}
      ]{norms_fields}
    }}
  ]
}}

Правила, обязательные к соблюдению:

1. Бери ТОЛЬКО цены для населения и ТОЛЬКО с учётом НДС, если документ печатает оба варианта.
   Цены для прочих потребителей и промышленности игнорируй.
2. Верни периоды, действующие сегодня и в будущем. Периоды, закончившиеся до сегодняшнего дня,
   не возвращай.
3. Числа возвращай числами, десятичный разделитель — точка. Ничего не вычисляй и не
   пересчитывай: ни цену за 1 м³ из цены за 1000 м³, ни цены с НДС из цен без НДС, ни плату
   по нормам — возвращай напечатанное.
4. Все планы одного периода делят его даты. Если цены меняются в разные даты, раздели год на
   периоды по всем этим датам и в каждый период включи все планы.
5. НИКОГДА не заполняй поле по памяти или по аналогии. Данных нет в документе — значит их нет.
   Если в документе нет цены основного плана, верни {{"periods": []}}.
"""

GAS_DISTRIBUTION_FIELDS = (
    '\n      "distributor": "название газораспределительной организации, как напечатано",\n'
    '      "distribution_rate": число — тариф на доставку (распределение) газа за ту же единицу, '
    'что и цены, или null, если он не напечатан,'
)

GAS_NORMS_FIELDS = (
    ',\n      "norms": список норм потребления газа на месяц для потребителей без счётчика, если '
    'документ их печатает, иначе null. Элемент: {"usage": "stove_with_hot_water" — газовая '
    'плита при централизованном горячем водоснабжении, "stove_without_hot_water" — плита без '
    'централизованного горячего водоснабжения и без водонагревателя, "stove_and_water_heater" — '
    'плита и газовый водонагреватель, "water_heater" — только водонагреватель, "heating" — '
    'отопление; "basis": "per_person" — на человека, "per_m2" — на 1 м² отапливаемой площади; '
    '"value": норма в м³ на месяц; "heating_season_only": true, если норма действует только '
    'в отопительный период, иначе false},\n'
    '      "norms_decree": "реквизиты документа, которым установлены нормы, как напечатано"'
)

CROSS_CHECK_TEMPLATE = """Найди в открытых источниках действующий тариф на {block_name}
для населения, {city_name}, поставщик {supplier}.

Верни СТРОГО такой JSON:
{{"rate": число или null, "effective_date": "YYYY-MM-DD или null", "source": "адрес страницы"}}

Нужна итоговая цена за единицу с НДС: {what}. Если уверенного ответа нет — верни null.
Не угадывай.
"""

CROSS_CHECK_WHAT = {
    "water": "сумма холодного водоснабжения и водоотведения за 1 {unit}",
    "hot_water": "цена 1 {unit} горячей воды",
    "heating": "цена 1 Гкал тепловой энергии",
}


def city_prompt(block: str, city_name: str, supplier: str, currency: str, unit: str,
                hint: str = "", today: str = "", aliases: list = None,
                heat_norms: bool = False) -> str:
    """The instruction for one city and one block.

    The date is passed in rather than left to the model: a decree usually lists a decade of
    periods, and a model with no idea what today is happily returns the ones from two years
    ago — which then look exactly like a fresh extraction.
    """
    today = today or date.today().strftime("%Y-%m-%d")
    supplier_line = f"Ожидаемый поставщик: {supplier}.\n" if supplier else ""
    if supplier and aliases:
        # Without this the model reads a name it was not told about as "the tariff is not here":
        # the Novosibirsk heat company is published as АО "СИБЭКО" and printed as НТСК.
        supplier_line += f"В документе он может называться иначе: {'; '.join(aliases)}.\n"
    hint_line = f"\nВажное уточнение по этому источнику: {hint}\n" if hint else ""
    return CITY_TEMPLATE.format(
        today=today,
        block_name=BLOCK_NAMES[block],
        city_name=city_name,
        supplier_line=supplier_line,
        hint_line=hint_line,
        currency=currency,
        fields=(PERIOD_FIELDS[block] + (HEAT_NORMS_FIELD if heat_norms else "")).format(
            unit=unit_name(unit)),
        no_math=NO_MATH[block].format(unit=unit_name(unit)),
    )


def electricity_prompt(region: str, currency: str, unit: str, plans: dict, today: str = "",
                       hint: str = "", supplier: str = "") -> str:
    """The instruction for one electricity source. `plans` is config's code -> {name, hint,
    default}: the groups of consumers to read, each with the line telling which rows are its."""
    lines = []
    for code, plan in plans.items():
        plan = plan or {}
        main = " (основная)" if plan.get("default") else ""
        detail = f" {plan['hint']}" if plan.get("hint") else ""
        lines.append(f"- {code}{main} — {plan.get('name') or code}.{detail}")
    return ELECTRICITY_TEMPLATE.format(
        today=today or date.today().strftime("%Y-%m-%d"),
        supplier_line=f"Ожидаемый поставщик: {supplier}.\n" if supplier else "",
        hint_line=f"\nВажное уточнение по этому источнику: {hint}\n" if hint else "",
        plans="\n".join(lines), region=region, currency=currency, unit=unit_name(unit))


def gas_prompt(city_name: str, supplier: str, currency: str, plans: dict, today: str = "",
               hint: str = "", distribution: bool = False, norms: bool = False) -> str:
    """The instruction for one city's gas source. Delivery and norms are asked only of a source
    config says prints them: a field the page has no answer for is a chance to fill it wrongly."""
    lines = []
    for code, plan in plans.items():
        plan = plan or {}
        main = " (основной)" if plan.get("default") else ""
        detail = f" {plan['hint']}" if plan.get("hint") else ""
        lines.append(f"- {code}{main} — {plan.get('name') or code}.{detail}")
    return GAS_TEMPLATE.format(
        today=today or date.today().strftime("%Y-%m-%d"),
        city_name=city_name, currency=currency, plans="\n".join(lines),
        supplier_line=f"Ожидаемый поставщик: {supplier}.\n" if supplier else "",
        hint_line=f"\nВажное уточнение по этому источнику: {hint}\n" if hint else "",
        distribution_fields=GAS_DISTRIBUTION_FIELDS if distribution else "",
        norms_fields=GAS_NORMS_FIELDS if norms else "")


def cross_check_prompt(block: str, city_name: str, supplier: str, unit: str) -> str:
    return CROSS_CHECK_TEMPLATE.format(
        block_name=BLOCK_NAMES[block],
        city_name=city_name,
        supplier=supplier,
        what=CROSS_CHECK_WHAT[block].format(unit=unit_name(unit)),
    )
