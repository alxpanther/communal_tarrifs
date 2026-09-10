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
        '      "tariff_type": "one_rate" или "two_rate"'
    ),
}

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

ELECTRICITY_TEMPLATE = """Извлеки из приведённого документа действующий тариф на
электроэнергию для населения.

Сегодня {today}.
Регион: {region}.
{hint_line}
Валюта: {currency}. Единица: {unit}.

Верни СТРОГО такой JSON и ничего кроме него:
{{
  "periods": [
    {{
      "from": "YYYY-MM-DD",
      "to": "YYYY-MM-DD или null",
      "base_rate": число — цена 1 {unit} по однотарифному счётчику, с НДС,
      "decree_info": "реквизиты документа, которым установлен тариф"
    }}
  ]
}}

Правила те же, что и для прочих тарифов: только для населения, только с НДС, все
периоды из документа, ничего не вычислять и не додумывать. Если тариф зависит от типа
плиты в квартире, бери вариант для домов с газовыми плитами. Если тарифа в документе
нет — верни {{"periods": []}}.
"""

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
                hint: str = "", today: str = "") -> str:
    """The instruction for one city and one block.

    The date is passed in rather than left to the model: a decree usually lists a decade of
    periods, and a model with no idea what today is happily returns the ones from two years
    ago — which then look exactly like a fresh extraction.
    """
    today = today or date.today().strftime("%Y-%m-%d")
    supplier_line = f"Ожидаемый поставщик: {supplier}.\n" if supplier else ""
    hint_line = f"\nВажное уточнение по этому источнику: {hint}\n" if hint else ""
    return CITY_TEMPLATE.format(
        today=today,
        block_name=BLOCK_NAMES[block],
        city_name=city_name,
        supplier_line=supplier_line,
        hint_line=hint_line,
        currency=currency,
        fields=PERIOD_FIELDS[block].format(unit=unit_name(unit)),
        no_math=NO_MATH[block].format(unit=unit_name(unit)),
    )


def electricity_prompt(region: str, currency: str, unit: str, today: str = "",
                       hint: str = "") -> str:
    return ELECTRICITY_TEMPLATE.format(
        today=today or date.today().strftime("%Y-%m-%d"),
        hint_line=f"\nВажное уточнение по этому источнику: {hint}\n" if hint else "",
        region=region, currency=currency, unit=unit_name(unit))


def cross_check_prompt(block: str, city_name: str, supplier: str, unit: str) -> str:
    return CROSS_CHECK_TEMPLATE.format(
        block_name=BLOCK_NAMES[block],
        city_name=city_name,
        supplier=supplier,
        what=CROSS_CHECK_WHAT[block].format(unit=unit_name(unit)),
    )
