import re
import statistics
from urllib.parse import urljoin, urlparse, quote_plus

import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template_string, request, jsonify


app = Flask(__name__)

MAX_PRODUCTS = 30
TIMEOUT = 20

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8",
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,image/webp,*/*;q=0.8"
    ),
}


# =========================================================
# HTML
# =========================================================

HTML = r"""
<!DOCTYPE html>

<html lang="ar" dir="rtl">

<head>

<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">

<title>Active Online — Trendyol Intelligence</title>

<script src="https://cdn.tailwindcss.com"></script>

<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

<script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>

<style>

body {
    font-family: Arial, sans-serif;
}

.report {
    white-space: pre-wrap;
    line-height: 2;
}

.card {
    transition: .2s;
}

.card:hover {
    transform: translateY(-3px);
}

@media print {

    body * {
        visibility: hidden;
    }

    #report,
    #report * {
        visibility: visible;
    }

    #report {
        position: absolute;
        left: 0;
        top: 0;
        width: 100%;
    }

    .no-print {
        display: none !important;
    }
}

</style>

</head>


<body class="bg-gray-100">

<div class="max-w-7xl mx-auto p-5">


<!-- HEADER -->

<div class="text-center mb-8 no-print">

<h1 class="text-4xl font-black text-blue-900">
Active Online
</h1>

<p class="text-xl text-gray-600">
Trendyol Intelligence
</p>

<p class="text-sm text-gray-500 mt-2">
تحليل المتاجر والمنتجات والمنافسة والأسعار
</p>

</div>


<!-- INPUT -->

<div class="bg-white rounded-2xl shadow p-7 mb-8 no-print">

<h2 class="text-2xl font-bold text-blue-900 mb-6">
🚀 تحليل متجر Trendyol
</h2>


<div class="grid md:grid-cols-3 gap-4 mb-5">

<div>

<label class="font-bold">
اسم المتجر
</label>

<input
id="storeName"
value="Trendyol Store"
class="w-full border rounded-xl p-3 mt-2"
>

</div>


<div>

<label class="font-bold">
الفئة
</label>

<input
id="category"
value="Home & Furniture"
class="w-full border rounded-xl p-3 mt-2"
>

</div>


<div>

<label class="font-bold">
الميزانية TL
</label>

<input
id="budget"
type="number"
value="10000"
class="w-full border rounded-xl p-3 mt-2"
>

</div>

</div>


<label class="font-bold">
رابط المتجر أو صفحة Trendyol
</label>

<div class="flex gap-3 mt-2">

<input
id="url"
placeholder="https://www.trendyol.com/magaza/..."
class="flex-1 border rounded-xl p-4"
>

<button
onclick="analyze()"
id="btn"
class="bg-blue-600 hover:bg-blue-700 text-white px-8 rounded-xl font-bold"
>
تحليل
</button>

</div>


<div
id="loading"
class="hidden mt-5 text-center text-blue-600 font-bold"
>
⏳ جاري التحليل...
</div>


<div
id="errorBox"
class="hidden mt-5 bg-red-50 border border-red-300 text-red-700 p-5 rounded-xl"
></div>


<!-- MANUAL MODE -->

<div
id="manualBox"
class="hidden mt-6 bg-yellow-50 border border-yellow-300 rounded-xl p-6"
>

<h3 class="font-bold text-lg mb-3">
⚠️ Trendyol رفض الاتصال من Render
</h3>

<p class="text-sm leading-7 mb-4">

هذا يعني أن Trendyol أعاد HTTP 403 للسيرفر.
لذلك لا نستطيع استخراج الصفحة مباشرة من Render.

يمكنك استخدام الوضع اليدوي بإدخال روابط منتجات Trendyol
الحقيقية، كل رابط في سطر.

</p>

<textarea
id="manualUrls"
rows="7"
placeholder="https://www.trendyol.com/....-p-123456
https://www.trendyol.com/....-p-789012"
class="w-full border rounded-xl p-4"
></textarea>

<button
onclick="manualAnalyze()"
class="mt-4 bg-yellow-600 text-white px-7 py-3 rounded-xl font-bold"
>
تحليل الروابط
</button>

</div>

</div>


<!-- RESULT -->

<div id="results" class="hidden">


<!-- STATS -->

<div class="grid md:grid-cols-5 gap-4 mb-8 no-print">

<div class="bg-blue-600 text-white rounded-2xl p-5">

<div>المنتجات</div>

<div id="total" class="text-3xl font-black">
0
</div>

</div>


<div class="bg-green-600 text-white rounded-2xl p-5">

<div>متوسط السعر</div>

<div id="avg" class="text-3xl font-black">
0
</div>

</div>


<div class="bg-purple-600 text-white rounded-2xl p-5">

<div>أقل سعر</div>

<div id="min" class="text-3xl font-black">
0
</div>

</div>


<div class="bg-indigo-600 text-white rounded-2xl p-5">

<div>أعلى سعر</div>

<div id="max" class="text-3xl font-black">
0
</div>

</div>


<div class="bg-orange-500 text-white rounded-2xl p-5">

<div>Opportunity</div>

<div id="score" class="text-3xl font-black">
0
</div>

</div>

</div>


<!-- CHARTS -->

<div class="grid md:grid-cols-2 gap-6 mb-8 no-print">


<div class="bg-white rounded-2xl shadow p-6">

<h3 class="font-bold text-xl mb-4">
📊 أسعار المنتجات
</h3>

<div class="h-80">

<canvas id="priceChart"></canvas>

</div>

</div>


<div class="bg-white rounded-2xl shadow p-6">

<h3 class="font-bold text-xl mb-4">
📈 مؤشرات المتجر
</h3>

<div class="h-80">

<canvas id="scoreChart"></canvas>

</div>

</div>

</div>


<!-- REPORT -->

<div
id="report"
class="bg-white rounded-2xl shadow p-8 mb-8"
>

<div class="flex justify-between border-b pb-5 mb-6">

<div>

<h2 class="text-3xl font-black text-blue-900">
التقرير الاستخباراتي الشامل
</h2>

<p
id="meta"
class="text-gray-500 mt-2"
></p>

</div>


<div class="flex gap-2 no-print">

<button
onclick="downloadPDF()"
class="bg-red-600 text-white px-4 py-2 rounded-xl font-bold"
>
PDF
</button>

<button
onclick="window.print()"
class="bg-green-600 text-white px-4 py-2 rounded-xl font-bold"
>
طباعة
</button>

</div>

</div>


<div
id="reportText"
class="report bg-gray-50 rounded-xl p-6"
></div>

</div>


<!-- PRODUCTS -->

<div class="bg-white rounded-2xl shadow p-7">

<h2 class="text-2xl font-bold mb-6">
🔗 المنتجات
</h2>

<div
id="products"
class="grid md:grid-cols-3 gap-5"
></div>

</div>


</div>

</div>


<script>

let chart1 = null;
let chart2 = null;


async function analyze() {

    const url =
        document.getElementById("url").value.trim();

    if (!url) {

        alert("ضع رابط Trendyol");

        return;
    }


    document
        .getElementById("loading")
        .classList.remove("hidden");


    document
        .getElementById("errorBox")
        .classList.add("hidden");


    document
        .getElementById("manualBox")
        .classList.add("hidden");


    document
        .getElementById("btn")
        .disabled = true;


    try {

        const response = await fetch(
            "/api/analyze",
            {
                method: "POST",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body: JSON.stringify({

                    storeName:
                        document.getElementById("storeName").value,

                    category:
                        document.getElementById("category").value,

                    budget:
                        document.getElementById("budget").value,

                    url: url

                })
            }
        );


        const data =
            await response.json();


        if (data.type === "TRENDYOL_403") {

            showManualMode();

            throw new Error(
                "Trendyol رفض الاتصال من Render."
            );
        }


        if (!response.ok) {

            throw new Error(
                data.error || "فشل التحليل"
            );
        }


        showResults(data);

    }

    catch (error) {

        document
            .getElementById("errorBox")
            .innerText =
                error.message;

        document
            .getElementById("errorBox")
            .classList.remove("hidden");

    }

    finally {

        document
            .getElementById("loading")
            .classList.add("hidden");

        document
            .getElementById("btn")
            .disabled = false;

    }

}



function showManualMode() {

    document
        .getElementById("manualBox")
        .classList.remove("hidden");

}



async function manualAnalyze() {

    const text =
        document.getElementById("manualUrls").value;


    const urls =
        text
        .split("\\n")
        .map(x => x.trim())
        .filter(Boolean);


    if (!urls.length) {

        alert("أدخل روابط المنتجات");

        return;
    }


    const response = await fetch(
        "/api/manual",
        {

            method: "POST",

            headers: {
                "Content-Type":
                    "application/json"
            },

            body: JSON.stringify({

                storeName:
                    document.getElementById("storeName").value,

                category:
                    document.getElementById("category").value,

                budget:
                    document.getElementById("budget").value,

                urls: urls

            })

        }
    );


    const data =
        await response.json();


    if (!response.ok) {

        alert(
            data.error ||
            "فشل التحليل"
        );

        return;
    }


    showResults(data);

}



function showResults(data) {

    const s =
        data.statistics;


    document
        .getElementById("total")
        .innerText =
            s.products_collected;


    document
        .getElementById("avg")
        .innerText =
            s.average_price + " TL";


    document
        .getElementById("min")
        .innerText =
            s.min_price + " TL";


    document
        .getElementById("max")
        .innerText =
            s.max_price + " TL";


    document
        .getElementById("score")
        .innerText =
            s.opportunity_score + "/100";


    document
        .getElementById("meta")
        .innerText =
            "المتجر: " +
            data.store_info.store_name;


    document
        .getElementById("reportText")
        .innerText =
            data.report;


    renderProducts(
        data.products
    );


    renderCharts(
        data.products,
        s
    );


    document
        .getElementById("results")
        .classList.remove("hidden");

}



function renderProducts(products) {

    const box =
        document.getElementById("products");

    box.innerHTML = "";


    products.forEach(p => {

        const div =
            document.createElement("div");


        div.className =
            "card border rounded-2xl p-5 bg-gray-50";


        const directLink =
            p.is_direct_product
            ? `
            <a
                href="${p.url}"
                target="_blank"
                rel="noopener noreferrer"
                class="block bg-green-600 text-white text-center p-3 rounded-xl font-bold"
            >
            🔗 فتح المنتج مباشرة
            </a>
            `
            :
            `
            <div class="bg-yellow-100 text-yellow-800 p-3 rounded-xl text-center text-sm">
            رابط المنتج غير متاح مباشرة
            </div>
            `;


        div.innerHTML = `

            ${
                p.image
                ?
                `<img
                    src="${escapeHtml(p.image)}"
                    class="w-full h-52 object-cover rounded-xl mb-4"
                >`
                :
                ""
            }


            <h3 class="font-bold mb-4">
                ${escapeHtml(p.title)}
            </h3>


            <div class="space-y-2 text-sm">

                <div class="flex justify-between">
                    <span>السعر</span>
                    <b>${p.price} TL</b>
                </div>


                <div class="flex justify-between">
                    <span>التقييم</span>
                    <b>${p.rating || "غير متاح"}</b>
                </div>


                <div class="flex justify-between">
                    <span>المراجعات</span>
                    <b>${p.review_count || "غير متاح"}</b>
                </div>


                <div class="flex justify-between">
                    <span>Opportunity</span>
                    <b>${p.opportunity_score}/100</b>
                </div>

            </div>


            <div class="mt-5">
                ${directLink}
            </div>

        `;


        box.appendChild(div);

    });

}



function escapeHtml(text) {

    return String(text || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");

}



function renderCharts(products, stats) {

    if (chart1)
        chart1.destroy();

    if (chart2)
        chart2.destroy();


    chart1 = new Chart(
        document.getElementById("priceChart"),
        {

            type: "bar",

            data: {

                labels:
                    products.map(
                        (_, i) =>
                            "منتج " + (i + 1)
                    ),

                datasets: [{

                    label: "السعر TL",

                    data:
                        products.map(
                            p => p.price
                        )

                }]

            },

            options: {
                responsive: true,
                maintainAspectRatio: false
            }

        }
    );


    chart2 = new Chart(
        document.getElementById("scoreChart"),
        {

            type: "radar",

            data: {

                labels: [
                    "السعر",
                    "SEO",
                    "التقييم",
                    "المراجعات",
                    "الفرصة"
                ],

                datasets: [{

                    label:
                        "Store Intelligence",

                    data: [

                        stats.price_score,

                        stats.seo_score,

                        stats.rating_score,

                        stats.review_score,

                        stats.opportunity_score

                    ]

                }]

            },

            options: {

                responsive: true,

                maintainAspectRatio: false,

                scales: {

                    r: {
                        beginAtZero: true,
                        max: 100
                    }

                }

            }

        }
    );

}



function downloadPDF() {

    html2pdf()
        .from(
            document.getElementById("report")
        )
        .set({

            margin: 10,

            filename:
                "ActiveOnline-Trendyol-Report.pdf",

            html2canvas: {
                scale: 2
            },

            jsPDF: {
                unit: "mm",
                format: "a4",
                orientation: "portrait"
            }

        })
        .save();

}

</script>

</body>
</html>
"""


# =========================================================
# TRENDYOL FUNCTIONS
# =========================================================

def fetch_trendyol(url):

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT,
            allow_redirects=True
        )

    except requests.exceptions.RequestException as e:

        raise Exception(
            "تعذر الاتصال بـ Trendyol: "
            + str(e)
        )


    if response.status_code == 403:

        raise PermissionError(
            "Trendyol returned HTTP 403"
        )


    if response.status_code == 429:

        raise Exception(
            "Trendyol طلب الانتظار بسبب كثرة الطلبات."
        )


    if response.status_code >= 400:

        raise Exception(
            f"Trendyol HTTP {response.status_code}"
        )


    return response.text



def product_url(url):

    if not url:
        return None


    absolute =
        urljoin(
            "https://www.trendyol.com",
            url
        )


    parsed =
        urlparse(absolute)


    if "trendyol.com" not in parsed.netloc:
        return None


    match =
        re.search(
            r"-p-(\d+)",
            parsed.path.lower()
        )


    if not match:
        return None


    return (
        "https://www.trendyol.com"
        + parsed.path
    )



def product_id(url):

    if not url:
        return None


    match =
        re.search(
            r"-p-(\d+)",
            url
        )


    return (
        match.group(1)
        if match
        else None
    )



def parse_price(text):

    if not text:
        return 0


    matches =
        re.findall(
            r"\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?",
            text
        )


    values = []


    for x in matches:

        try:

            x =
                x.replace(
                    ".",
                    ""
                ).replace(
                    ",",
                    "."
                )


            n = float(x)


            if 1 <= n <= 1000000:

                values.append(n)

        except:
            pass


    return (
        round(values[0], 2)
        if values
        else 0
    )



def parse_rating(text):

    if not text:
        return None


    matches =
        re.findall(
            r"[0-5](?:[.,]\d+)?",
            text
        )


    for x in matches:

        try:

            n =
                float(
                    x.replace(",", ".")
                )


            if 0 <= n <= 5:

                return n

        except:
            pass


    return None



def parse_reviews(text):

    if not text:
        return None


    numbers =
        re.findall(
            r"\d[\d.]*",
            text
        )


    values = []


    for x in numbers:

        try:

            n =
                int(
                    x.replace(".", "")
                )

            if n > 0:
                values.append(n)

        except:
            pass


    return (
        max(values)
        if values
        else None
    )



# =========================================================
# EXTRACT PRODUCTS
# =========================================================

def extract_products(html):

    soup =
        BeautifulSoup(
            html,
            "html.parser"
        )


    products = []

    seen = set()


    for a in soup.find_all(
        "a",
        href=True
    ):

        url =
            product_url(
                a.get("href")
            )


        if not url:
            continue


        pid =
            product_id(url)


        if not pid:
            continue


        if pid in seen:
            continue


        seen.add(pid)


        title =
            a.get("title") or \
            a.get("aria-label") or \
            a.get_text(
                " ",
                strip=True
            )


        img =
            a.find("img")


        image = ""


        if img:

            image =
                img.get("src") or \
                img.get("data-src") or \
                ""


            if image.startswith("//"):

                image =
                    "https:" + image


        parent =
            a.parent


        text =
            parent.get_text(
                " ",
                strip=True
            ) if parent else ""


        products.append({

            "id": pid,

            "title":
                title[:250] or
                "Trendyol Product " + pid,

            "price":
                parse_price(text),

            "rating":
                parse_rating(text),

            "review_count":
                parse_reviews(text),

            "image":
                image,

            "url":
                url,

            "is_direct_product":
                True

        })


        if len(products) >= MAX_PRODUCTS:
            break


    return products



# =========================================================
# MANUAL URL MODE
# =========================================================

def products_from_urls(urls):

    products = []


    for url in urls:

        clean =
            product_url(url)


        if not clean:
            continue


        pid =
            product_id(clean)


        products.append({

            "id": pid,

            "title":
                "Trendyol Product " + pid,

            "price": 0,

            "rating": None,

            "review_count": None,

            "image": "",

            "url": clean,

            "is_direct_product": True,

            "opportunity_score": 50

        })


    return products



# =========================================================
# SCORING
# =========================================================

def score_products(products):

    prices = [
        p["price"]
        for p in products
        if p["price"] > 0
    ]


    if prices:

        avg =
            statistics.mean(prices)

        spread =
            statistics.pstdev(prices)

        price_score =
            max(
                0,
                min(
                    100,
                    round(
                        70 -
                        ((spread / avg) * 60)
                    )
                )
            )

    else:

        price_score = 50


    seo_scores = []


    for p in products:

        title =
            p["title"]


        score = 50


        if 30 <= len(title) <= 120:
            score += 25


        if len(title.split()) >= 5:
            score += 15


        seo_scores.append(
            min(100, score)
        )


    seo_score =
        round(
            statistics.mean(
                seo_scores
            )
        ) if seo_scores else 50


    ratings = [
        p["rating"]
        for p in products
        if p["rating"] is not None
    ]


    rating_score = (
        round(
            statistics.mean(ratings)
            / 5 * 100
        )
        if ratings
        else 50
    )


    reviews = [
        p["review_count"]
        for p in products
        if p["review_count"]
    ]


    review_score = 50


    if reviews:

        review_score =
            min(
                100,
                round(
                    30 +
                    (statistics.mean(reviews) ** .5) * 8
                )
            )


    opportunity =
        round(

            price_score * .25 +

            seo_score * .25 +

            rating_score * .20 +

            review_score * .30

        )


    for p in products:

        ps = 50


        if p["price"] > 0:
            ps += 10


        if len(p["title"]) >= 40:
            ps += 10


        if p["rating"]:

            if p["rating"] >= 4.5:
                ps += 15

            elif p["rating"] >= 4:
                ps += 8


        if p["review_count"]:

            if p["review_count"] >= 1000:
                ps += 15

            elif p["review_count"] >= 100:
                ps += 10

            elif p["review_count"] >= 20:
                ps += 5


        p["opportunity_score"] =
            min(100, ps)


    return {

        "products_collected":
            len(products),

        "min_price":
            round(min(prices), 2)
            if prices else 0,

        "max_price":
            round(max(prices), 2)
            if prices else 0,

        "average_price":
            round(
                statistics.mean(prices),
                2
            ) if prices else 0,

        "price_score":
            price_score,

        "seo_score":
            seo_score,

        "rating_score":
            rating_score,

        "review_score":
            review_score,

        "opportunity_score":
            opportunity

    }



# =========================================================
# REPORT
# =========================================================

def make_report(
    store,
    category,
    budget,
    products,
    stats
):

    top =
        sorted(
            products,
            key=lambda x:
                x["opportunity_score"],
            reverse=True
        )[:5]


    top_text = ""


    for i, p in enumerate(
        top,
        1
    ):

        top_text += (
            f"{i}. {p['title']}\n"
            f"   السعر: {p['price']} TL\n"
            f"   Opportunity Score: "
            f"{p['opportunity_score']}/100\n"
            f"   الرابط المباشر: {p['url']}\n\n"
        )


    revenue_2 =
        budget * 2

    revenue_3 =
        budget * 3

    revenue_4 =
        budget * 4


    return f"""

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 ACTIVE ONLINE
TRENDYOL INTELLIGENCE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🏪 المتجر:
{store}

📂 الفئة:
{category}

📦 عدد المنتجات المحللة:
{stats['products_collected']}


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. الملخص التنفيذي
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

متوسط السعر:
{stats['average_price']} TL

أقل سعر:
{stats['min_price']} TL

أعلى سعر:
{stats['max_price']} TL

Opportunity Score:
{stats['opportunity_score']}/100


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2. تحليل الأسعار
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Price Score:
{stats['price_score']}/100

يتم تقييم هيكل الأسعار ومدى تنوع
النطاق السعري للمنتجات.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
3. SEO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SEO Score:
{stats['seo_score']}/100

التوصيات:

• وضع الكلمة المفتاحية الرئيسية في بداية العنوان.
• كتابة عناوين واضحة باللغة التركية.
• استخدام كلمات تصف النوع والخامة والاستخدام.
• تجنب تكرار الكلمات بلا قيمة.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
4. التقييمات والمراجعات
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Rating Score:
{stats['rating_score']}/100

Review Score:
{stats['review_score']}/100


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
5. أفضل المنتجات
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{top_text}


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
6. استراتيجية الإعلانات
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

الميزانية:
{budget:,.2f} TL

اقتراح مبدئي:

Meta Ads:
40%

Google:
25%

Trendyol Ads:
25%

Retargeting:
10%


ابدأ باختبار عدد محدود من المنتجات،
ثم قم بزيادة الميزانية فقط للمنتجات
التي تظهر نتائج فعلية.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
7. السيناريو المالي
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ تقديرات وليست مبيعات فعلية.

ROAS 2x:
{revenue_2:,.2f} TL

ROAS 3x:
{revenue_3:,.2f} TL

ROAS 4x:
{revenue_4:,.2f} TL


لا يتم اعتبار هذه الأرقام توقعاً مضموناً.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
8. خطة 30 يوم
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

الأسبوع 1:
تحسين المنتجات والعناوين والصور.

الأسبوع 2:
اختبار الإعلانات.

الأسبوع 3:
إيقاف المنتجات الضعيفة
وزيادة المنتجات الرابحة.

الأسبوع 4:
تحليل النتائج وبناء خطة الشهر التالي.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
9. أهم التوصيات
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

• التركيز على المنتجات ذات Opportunity Score مرتفع.
• تحسين SEO.
• تحسين الصور.
• اختبار عروض وأسعار مختلفة.
• عدم الاعتماد على منتج واحد.
• مراقبة المنافسين باستمرار.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Active Online
Trendyol Intelligence
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""


# =========================================================
# ROUTES
# =========================================================

@app.route("/")
def home():

    return render_template_string(
        HTML
    )



@app.route(
    "/api/analyze",
    methods=["POST"]
)
def analyze():

    data =
        request.get_json(
            silent=True
        ) or {}


    store =
        str(
            data.get(
                "storeName",
                "Trendyol Store"
            )
        )


    category =
        str(
            data.get(
                "category",
                "عام"
            )
        )


    budget =
        float(
            data.get(
                "budget",
                10000
            )
        )


    url =
        str(
            data.get(
                "url",
                ""
            )
        ).strip()


    if not url:

        return jsonify({
            "error":
                "أدخل رابط Trendyol"
        }), 400


    try:

        html =
            fetch_trendyol(
                url
            )


    except PermissionError:

        return jsonify({

            "type":
                "TRENDYOL_403",

            "error":
                "Trendyol رفض الاتصال من Render."

        }), 403


    except Exception as e:

        return jsonify({
            "error":
                str(e)
        }), 502


    products =
        extract_products(
            html
        )


    if not products:

        return jsonify({

            "error":
                "لم نجد منتجات Product URLs حقيقية داخل الصفحة."

        }), 422


    stats =
        score_products(
            products
        )


    report =
        make_report(
            store,
            category,
            budget,
            products,
            stats
        )


    return jsonify({

        "status":
            "success",

        "store_info": {

            "store_name":
                store,

            "url":
                url

        },

        "statistics":
            stats,

        "products":
            products,

        "report":
            report

    })



@app.route(
    "/api/manual",
    methods=["POST"]
)
def manual():

    data =
        request.get_json(
            silent=True
        ) or {}


    store =
        str(
            data.get(
                "storeName",
                "Trendyol Store"
            )
        )


    category =
        str(
            data.get(
                "category",
                "عام"
            )
        )


    budget =
        float(
            data.get(
                "budget",
                10000
            )
        )


    urls =
        data.get(
            "urls",
            []
        )


    products =
        products_from_urls(
            urls
        )


    if not products:

        return jsonify({

            "error":
                "لم يتم العثور على روابط منتجات صحيحة. "
                "يجب أن يحتوي الرابط على -p-رقم."

        }), 422


    stats =
        score_products(
            products
        )


    report =
        make_report(
            store,
            category,
            budget,
            products,
            stats
        )


    return jsonify({

        "status":
            "success",

        "store_info": {

            "store_name":
                store

        },

        "statistics":
            stats,

        "products":
            products,

        "report":
            report

    })


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
