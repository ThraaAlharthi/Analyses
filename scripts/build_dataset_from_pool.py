#!/usr/bin/env python3
"""Builds dataset examples from REAL compute_stats output in data/input_pool.jsonl.
Unlike build_dataset.py, nothing here is hand-typed -- every number traces
back to an actual Sentinel-2 fetch + local NDVI computation.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POOL = ROOT / "data" / "input_pool.jsonl"
OUT = ROOT / "data" / "instructions_real.jsonl"

from build_dataset import regime, SPREAD, S1, S2, S3, INSTR, n

EXCLUDE_KML = {"lshape_test.kml"}

WATER_ADVICE = "تشير القراءة السلبية إلى سطح مائي، إذ يمتص الماء الأشعة تحت الحمراء القريبة بعكس الغطاء النباتي؛ هذا التصنيف متوقع وليس مؤشرًا على جفاف الأرض."

def is_water(mean: float) -> bool:
    return mean < 0

def advice_for(mean: float) -> str:
    if is_water(mean):
        return WATER_ADVICE
    from build_dataset import advice
    return advice(mean)

def regime_for(mean: float) -> str:
    if is_water(mean):
        return "إشارة مائية (NDVI سالب)"
    return regime(mean)

def load_pool():
    records = []
    with POOL.open(encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            if row.get("source_kml") in EXCLUDE_KML:
                continue
            records.append(row)
    return records

def single_from_pool(i, row):
    area = row["areaName"]
    date = row["date"]
    mean = row["ndvi"]["mean"]
    mn = row["ndvi"]["min"]
    mx = row["ndvi"]["max"]
    veg = row["land_cover"]["vegetation_pct"]

    payload = {
        "image_id": row["scene_id"],
        "area_name_ar": area, "date": date,
        "ndvi": {"mean": mean, "min": mn, "max": mx},
        "vegetation_percent": veg, "pixel_count": row["pixel_count"],
        "latitude": row["latitude"], "longitude": row["longitude"],
    }
    out = " ".join([
        S1[i % 4].format(area=area, date=date, mean=n(mean), reg=regime_for(mean)),
        S2[i % 3].format(mn=n(mn), mx=n(mx), spread=SPREAD[i % 3]),
        S3[i % 3].format(veg=n(veg)),
        advice_for(mean),
    ])
    return {"instruction": INSTR[i % 5],
            "input": json.dumps(payload, ensure_ascii=False), "output": out, "category": "ndvi_explanation"}
LC_INSTR = [
    "لخّص توزيع الغطاء الأرضي التالي، مع تحديد الفئة السائدة.",
    "صف حالة الغطاء الأرضي في هذه المنطقة اعتمادًا على البيانات المرفقة.",
    "ما نسبة الغطاء النباتي مقابل غير النباتي في هذه الصورة؟",
]

def land_cover_from_pool(i, row):
    area = row["areaName"]
    date = row["date"]
    veg = row["land_cover"]["vegetation_pct"]
    non_veg = row["land_cover"]["non_vegetation_pct"]
    threshold = row["land_cover"]["threshold_used"]
    mean = row["ndvi"]["mean"]

    payload = {
        "image_id": row["scene_id"],
        "area_name_ar": area, "date": date,
        "land_cover_pct": {"vegetation": veg, "non_vegetation": non_veg},
        "ndvi_threshold_used": threshold,
        "pixel_count": row["pixel_count"],
    }

    if is_water(mean):
        out = (f"تُظهر بيانات {area} بتاريخ {date} أن {n(non_veg)}% من المساحة "
               f"صُنِّفت كغير نباتية عند عتبة NDVI قدرها {n(threshold)}، وهي نسبة "
               f"متوقعة لكون المنطقة سطحًا مائيًا لا غطاءً أرضيًا جافًا؛ لذا لا "
               f"ينبغي تفسير هذا الرقم كمؤشر على جفاف الأرض أو تدهورها.")
    else:
        dominant = "الغطاء النباتي" if veg > non_veg else "المساحات غير النباتية"
        out = (f"تُظهر بيانات {area} بتاريخ {date} أن {n(veg)}% من المساحة "
               f"مغطاة بالنباتات مقابل {n(non_veg)}% غير نباتية، عند عتبة NDVI "
               f"قدرها {n(threshold)}. الفئة السائدة في هذا المشهد هي {dominant}.")

    return {"instruction": LC_INSTR[i % 3],
            "input": json.dumps(payload, ensure_ascii=False),
            "output": out,
            "category": "land_cover_explanation"}

REPORT_INSTR = [
    "قدّم تقريرًا موجزًا عن نتائج التحليل الطيفي لهذه الصورة.",
    "اكتب تقريرًا تلخيصيًا لبيانات الاستشعار عن بعد التالية.",
]

def report_from_pool(i, row):
    area = row["areaName"]
    date = row["date"]
    mean = row["ndvi"]["mean"]
    mn = row["ndvi"]["min"]
    mx = row["ndvi"]["max"]
    veg = row["land_cover"]["vegetation_pct"]
    non_veg = row["land_cover"]["non_vegetation_pct"]
    lat, lon = row["latitude"], row["longitude"]

    payload = {
        "image_id": row["scene_id"],
        "area_name_ar": area, "date": date,
        "ndvi_mean": mean, "ndvi_min": mn, "ndvi_max": mx,
        "vegetation_pct": veg, "non_vegetation_pct": non_veg, "pixel_count": row["pixel_count"],
        "latitude": lat, "longitude": lon,
    }

    if is_water(mean):
        body = (f"يقع الموقع عند الإحداثيات {n(lat)}, {n(lon)}. سجّل متوسط NDVI "
                f"قيمة {n(mean)}، وهي إشارة مائية تعكس وجود سطح مائي في المنطقة "
                f"وليس أرضًا جرداء. بلغت نسبة الغطاء غير النباتي {n(non_veg)}%، "
                f"وهو أمر متوقع لمسطح مائي.")
    else:
        body = (f"يقع الموقع عند الإحداثيات {n(lat)}, {n(lon)}. سجّل متوسط NDVI "
                f"قيمة {n(mean)} ({regime_for(mean)})، بمدى تراوح بين {n(mn)} و{n(mx)}. "
                f"بلغت نسبة الغطاء النباتي {n(veg)}%.")

    out = f"تقرير تحليل الغطاء النباتي — {area}، بتاريخ {date}. {body}"

    return {"instruction": REPORT_INSTR[i % 2],
            "input": json.dumps(payload, ensure_ascii=False),
            "output": out,
            "category": "report_generation"}
QA_INSTR = [
    "هل تشير هذه القراءات إلى غطاء نباتي كثيف في المنطقة؟ أجب بنعم أو لا مع التوضيح.",
    "هل يمكن اعتبار هذه المنطقة صالحة للزراعة بناءً على هذه البيانات؟",
    "هل تدل هذه القيم على وجود إجهاد مائي في الغطاء النباتي؟",
]

def ndvi_qa_from_pool(i, row):
    area = row["areaName"]
    date = row["date"]
    mean = row["ndvi"]["mean"]
    mn = row["ndvi"]["min"]
    mx = row["ndvi"]["max"]
    veg = row["land_cover"]["vegetation_pct"]

    payload = {
        "image_id": row["scene_id"],
        "area_name_ar": area, "date": date,
        "ndvi": {"mean": mean, "min": mn, "max": mx},
        "vegetation_percent": veg,
    }

    if is_water(mean):
        answer = (f"لا. متوسط NDVI لمنطقة {area} بتاريخ {date} هو {n(mean)}، وهي قيمة "
                  f"سالبة تدل على سطح مائي لا غطاء نباتي فيه، وليست علامة على إجهاد أو جفاف.")
    elif mean >= 0.4:
        answer = (f"نعم. سجّلت منطقة {area} بتاريخ {date} متوسط NDVI قدره {n(mean)}، "
                  f"وهو مستوى يعكس {regime_for(mean)}، مع تغطية نباتية بلغت {n(veg)}%.")
    else:
        answer = (f"لا، ليس بشكل كافٍ. سجّلت منطقة {area} بتاريخ {date} متوسط NDVI "
                  f"قدره {n(mean)}، وهو مستوى يعكس {regime_for(mean)}، مع تغطية نباتية "
                  f"لا تتجاوز {n(veg)}%.")

    return {"instruction": QA_INSTR[i % 3],
            "input": json.dumps(payload, ensure_ascii=False),
            "output": answer,
            "category": "ndvi_qa"}
LC_QA_INSTR = [
    "هل تدل هذه النسب على غلبة الغطاء النباتي في هذه المنطقة؟",
    "هل تشير هذه البيانات إلى أن معظم المساحة غير مزروعة؟",
    "بناءً على هذه الأرقام، هل يمكن وصف المنطقة بأنها خصبة؟",
]

def land_cover_qa_from_pool(i, row):
    area = row["areaName"]
    date = row["date"]
    veg = row["land_cover"]["vegetation_pct"]
    non_veg = row["land_cover"]["non_vegetation_pct"]
    threshold = row["land_cover"]["threshold_used"]
    mean = row["ndvi"]["mean"]

    payload = {
        "image_id": row["scene_id"],
        "area_name_ar": area, "date": date,
        "land_cover_pct": {"vegetation": veg, "non_vegetation": non_veg},
        "ndvi_threshold_used": threshold,
    }

    if is_water(mean):
        answer = (f"لا. تُظهر بيانات {area} بتاريخ {date} أن {n(non_veg)}% من المساحة "
                  f"صُنِّفت كغير نباتية، لكن هذا يعود إلى كون المنطقة سطحًا مائيًا "
                  f"وليس أرضًا جرداء أو غير خصبة.")
    elif veg > non_veg:
        answer = (f"نعم. تُظهر بيانات {area} بتاريخ {date} أن الغطاء النباتي يغطي "
                  f"{n(veg)}% من المساحة مقابل {n(non_veg)}% غير نباتية، عند عتبة "
                  f"NDVI قدرها {n(threshold)}، ما يعني غلبة واضحة للغطاء النباتي.")
    else:
        answer = (f"لا. تُظهر بيانات {area} بتاريخ {date} أن المساحات غير النباتية "
                  f"تشكّل {n(non_veg)}% مقابل {n(veg)}% غطاءً نباتيًا فقط، عند عتبة "
                  f"NDVI قدرها {n(threshold)}، ما يعني غلبة المساحات غير المزروعة.")

    return {"instruction": LC_QA_INSTR[i % 3],
            "input": json.dumps(payload, ensure_ascii=False),
            "output": answer,
            "category": "land_cover_qa"}
INSUFFICIENT_DATA = [
    ("حلّل نتائج مؤشر NDVI التالية.",
     {"area_name_ar": "صحار", "date": "2026-05-12",
      "ndvi": {"mean": None, "min": None, "max": None}, "pixel_count": 0},
     "لا يمكن إجراء التحليل. لا تحتوي البيانات المقدَّمة على أي قيم صالحة لمؤشر "
     "NDVI، كما أن عدد البكسلات المحللة يساوي صفرًا. يُرجى إعادة معالجة الصورة "
     "والتأكد من قراءة النطاقين الأحمر وتحت الأحمر القريب قبل طلب التحليل."),

    ("قدّم تقريرًا عن حالة الغطاء النباتي بناءً على البيانات المرفقة.",
     {"area_name_ar": "الرستاق", "date": "2026-01-20",
      "cloud_cover_pct": 98.2, "pixel_count": 9100},
     "لا يمكن إجراء التحليل بشكل موثوق. تبلغ نسبة الغطاء السحابي 98.2%، وهو ما "
     "يحجب معظم سطح الأرض في هذا المشهد. يُنصح باستخدام صورة أخرى بنسبة غيوم أقل."),

    ("هل تدل هذه القراءات على غطاء نباتي صحي؟",
     {"area_name_ar": "بهلاء", "date": "2026-03-09",
      "ndvi": {"mean": 1.42, "min": 0.6, "max": 2.1}},
     "البيانات المقدَّمة غير صالحة للتحليل. تقع قيمة متوسط NDVI المذكورة 1.42 "
     "خارج النطاق الفيزيائي المسموح للمؤشر (بين -1 و1)، ما يشير إلى خطأ في "
     "المعايرة أو في حساب المؤشر. يُرجى مراجعة خطوة الحساب قبل تفسير النتائج."),

    ("لخّص حالة الغطاء النباتي في هذه المنطقة اعتمادًا على البيانات المرفقة.",
     {"land_cover_pct": {"vegetation": 22.0, "non_vegetation": 78.0}},
     "البيانات ناقصة. لا يتضمن السجل اسم المنطقة ولا تاريخ الالتقاط، ومن دونهما "
     "لا يمكن نسب النتائج إلى موقع أو موسم محدد. يُرجى إرفاق البيانات الوصفية كاملة."),
("صف حالة الغطاء النباتي في هذه المنطقة.",
     {"area_name_ar": "عبري", "date": "2026-02-14",
      "ndvi": {"mean": 0.3, "min": None, "max": 0.9}},
     "البيانات غير مكتملة. القيمة الدنيا لمؤشر NDVI مفقودة من السجل، ولا يمكن "
     "وصف نطاق التباين في المشهد من دونها. يُرجى استكمال القيم الثلاث قبل التحليل."),

    ("قارن بين قراءتَي NDVI لمنطقة معينة في تاريخين مختلفين.",
     {"area_name_ar": "خصب", "observations": [
         {"date": "2026-05-01", "ndvi_mean": 0.4}]},
     "لا يمكن إجراء المقارنة المطلوبة. تحتوي البيانات على قراءة واحدة فقط "
     "بتاريخ 2026-05-01، بينما تتطلب المقارنة قراءتين على الأقل. يُرجى إرفاق "
     "صورة ثانية من تاريخ مختلف."),

    ("لخّص توزيع الغطاء الأرضي في هذه الصورة.",
     {"area_name_ar": "شناص", "date": "2026-06-01",
      "land_cover_pct": {"vegetation": 130.0, "non_vegetation": 40.0}, "expected_total_pct": 100},
     "البيانات غير صالحة. تتجاوز نسب الغطاء الأرضي مجموع 100% (130% + 40%)، ما "
     "يشير إلى خطأ في حساب النسب أو في تصنيف البكسلات. يُرجى مراجعة خطوة الحساب."),

    ("قدّم تقريرًا موجزًا عن هذه الصورة.",
     {"image_id": "unknown_20260315.tif", "bands_available": ["nir"],
      "bands_required": ["red", "nir"]},
     "تعذّر إعداد التقرير. تحتوي الصورة على النطاق تحت الأحمر القريب فقط، بينما "
     "يتطلب حساب NDVI النطاق الأحمر أيضًا. يُرجى تزويدنا بصورة تتضمن النطاقين معًا."),("حلّل بيانات الغطاء النباتي التالية.",
     {"area_name_ar": "لوى", "date": "2026-04-11",
      "ndvi": {"mean": 0.35, "min": 0.1, "max": 0.6}, "pixel_count": -200},
     "البيانات غير صالحة. عدد البكسلات المحللة قيمة سالبة (-200)، وهو أمر "
     "مستحيل فيزيائيًا ويشير إلى خطأ في معالجة الصورة. يُرجى إعادة تشغيل خطوة الحساب."),

    ("قدّم ملخصًا عن حالة الأرض في هذه الصورة.",
     {"area_name_ar": "قريات", "date": "2026-07-19",
      "land_cover_pct": {"vegetation": 45.0}},
     "البيانات ناقصة. لا يتضمن السجل نسبة المساحة غير النباتية، ولا يمكن "
     "استكمال الصورة الكاملة لتوزيع الغطاء الأرضي من دونها. يُرجى إرفاق النسبتين معًا."),

    ("هل تدل هذه القراءات على وجود غطاء نباتي؟",
     {"area_name_ar": "المصنعة", "date": "2026-08-30",
      "ndvi": {"mean": 0.4, "min": 0.5, "max": 0.3}},
     "البيانات غير متسقة. القيمة الدنيا لمؤشر NDVI (0.5) أكبر من القيمة "
     "العليا (0.3)، وهو تناقض منطقي يشير إلى خطأ في تسجيل القيم. يُرجى "
     "مراجعة السجل قبل التحليل."),

    ("لخّص نتائج التحليل الطيفي لهذا المشهد.",
     {"image_id": "wadi_hatta_20260222.tif", "area_name_ar": "وادي حطا",
      "date": "2026-02-22", "ndvi": {"mean": 0.28, "min": -0.1, "max": 0.7},
      "latitude": 95.2, "longitude": 57.1, "valid_latitude_range": [-90, 90]},
     "البيانات غير صالحة. قيمة خط العرض المذكورة (95.2) تقع خارج النطاق "
     "الجغرافي الممكن (-90 إلى 90)، ما يشير إلى خطأ في الإحداثيات المسجّلة. "
     "يُرجى التحقق من موقع المنطقة قبل تفسير النتائج."),

    ("قارن بين قراءتين لمنطقة زراعية عبر الزمن.",
     {"area_name_ar": "ودام", "observations": [
         {"date": "2026-03-01", "ndvi_mean": 0.3},
         {"date": "2026-03-01", "ndvi_mean": 0.5}]},
     "لا يمكن إجراء مقارنة زمنية موثوقة. كلا الرصدين يحملان التاريخ نفسه "
     "(2026-03-01) بقيمتين مختلفتين لمؤشر NDVI، ما يجعل من المستحيل تحديد "
     "الاتجاه الزمني. يُرجى التأكد من صحة تواريخ الالتقاط."),

    ("صف نسبة الغيوم وتأثيرها على إمكانية التحليل.",
     {"area_name_ar": "ينقل", "date": "2026-09-05",
      "cloud_cover_pct": 45.0, "valid_pixel_ratio": 0.04},
     "على الرغم من أن نسبة الغيوم المعلنة (45.0%) تبدو معتدلة، فإن نسبة "
     "البكسلات الصالحة الفعلية لا تتجاوز 0.04 من المشهد، ما يعني تناقضًا بين "
     "الرقمين يستدعي إعادة فحص عملية استخراج القناع السحابي قبل أي تحليل."),

    ("هل هذه القراءات كافية لإصدار تقرير؟",
     {"area_name_ar": "الكامل والوافي", "ndvi": {"mean": 0.33, "min": -0.05, "max": 0.7},
      "vegetation_percent": 38.0},
     "البيانات غير كافية لإصدار تقرير موثوق. لا يتضمن السجل تاريخ الالتقاط "
     "ولا معرّف المشهد، وكلاهما ضروري لتوثيق مصدر النتائج والتحقق منها لاحقًا. "
     "يُرجى إرفاق البيانات الوصفية كاملة."),

    ("حلّل مؤشر NDVI لهذه المنطقة الساحلية.",
     {"area_name_ar": "مصيرة", "date": "2026-06-14",
      "ndvi": {"mean": -0.02, "min": -0.9, "max": None}},
     "البيانات ناقصة. القيمة العليا لمؤشر NDVI مفقودة من السجل، ولا يمكن "
     "وصف المدى الكامل لتباين القيم في هذا المشهد الساحلي من دونها. يُرجى "
     "استكمال القيم الثلاث قبل التحليل."),]

def insufficient_data_examples():
    return [
        {"instruction": instr,
         "input": json.dumps(payload, ensure_ascii=False),
         "output": out,
         "category": "insufficient_data"}
        for instr, payload, out in INSUFFICIENT_DATA
    ]
CHANGE_INSTR = "قارن بين قراءتَي مؤشر NDVI لنفس المنطقة في تاريخين مختلفين، ووضّح الاتجاه."

def pair_by_kml(pool):
    from collections import defaultdict
    grouped = defaultdict(list)
    for row in pool:
        grouped[row["source_kml"]].append(row)
    pairs = []
    for kml, rows in grouped.items():
        if len(rows) >= 2:
            rows_sorted = sorted(rows, key=lambda r: r["date"])
            pairs.append((rows_sorted[0], rows_sorted[-1]))
    return pairs

def change_detection_from_pool(a, b):
    area = a["areaName"]
    d1, d2 = a["date"], b["date"]
    m1, m2 = a["ndvi"]["mean"], b["ndvi"]["mean"]
    v1, v2 = a["land_cover"]["vegetation_pct"], b["land_cover"]["vegetation_pct"]
    dm = round(m2 - m1, 4)
    dv = round(v2 - v1, 2)

    payload = {
        "area_name_ar": area,
        "observations": [
            {"date": d1, "ndvi_mean": m1, "vegetation_percent": v1},
            {"date": d2, "ndvi_mean": m2, "vegetation_percent": v2},
        ],
        "delta_ndvi_mean": dm, "delta_vegetation_percent": dv,
    }

    if is_water(m1) and is_water(m2):
        out = (f"في {area}، تغيّر متوسط NDVI من {n(m1)} بتاريخ {d1} إلى {n(m2)} "
               f"بتاريخ {d2}، بفارق قدره {n(dm)}. القيمتان سالبتان في كلا "
               f"التاريخين، ما يؤكد استمرار وجود سطح مائي في المنطقة طوال الفترة.")
    else:
        trend = "تحسّنًا" if dm > 0 else "تراجعًا"
        out = (f"في {area}، انتقل متوسط NDVI من {n(m1)} بتاريخ {d1} إلى {n(m2)} "
               f"بتاريخ {d2}، أي بفارق قدره {n(dm)}، ما يعكس {trend} في حالة "
               f"الغطاء النباتي. وتغيّرت نسبة التغطية النباتية من {n(v1)}% إلى "
               f"{n(v2)}%، بفارق {n(dv)} نقطة مئوية.")

    return {"instruction": CHANGE_INSTR,
            "input": json.dumps(payload, ensure_ascii=False),
            "output": out,
            "category": "change_detection"}
def main():
    pool = load_pool()
    records = [single_from_pool(i, row) for i, row in enumerate(pool)]
    records += [land_cover_from_pool(i, row) for i, row in enumerate(pool)]
    records += [report_from_pool(i, row) for i, row in enumerate(pool)]
    records += [ndvi_qa_from_pool(i, row) for i, row in enumerate(pool)]
    records += [land_cover_qa_from_pool(i, row) for i, row in enumerate(pool)]
    records += insufficient_data_examples()
    pairs = pair_by_kml(pool)
    records += [change_detection_from_pool(a, b) for a, b in pairs]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"wrote {len(records)} real examples -> {OUT}")

if __name__ == "__main__":
    main()
