import re
import statistics
from urllib.parse import urljoin, urlparse, parse_qs, quote_plus

import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template_string, request, jsonify


app = Flask(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}

TIMEOUT = 20
MAX_PRODUCTS = 30


# ============================================================
# HTML
# ============================================================

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <title>Active Online — Trendyol Intelligence</title>

    <link
        href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css"
        rel="stylesheet"
    >

    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>

    <style>

        body {
            font-family: Arial, sans-serif;
        }

        .report-text {
            white-space: pre-wrap;
            line-height: 2;
        }

        .product-card {
            transition: all .2s ease;
        }

        .product-card:hover {
            transform: translateY(-3px);
        }

        @media print {

            body * {
                visibility: hidden;
            }

            #printableReport,
            #printableReport * {
                visibility: visible;
            }

            #printableReport {
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


<body class="bg-gray-100 text-gray-900">

<div class="container mx-auto px-4 py-8 max-w-7xl">

    <!-- HEADER -->

    <header class="text-center mb-10 no-print">

        <h1 class="text-4xl font-extrabold text-blue-900">
            Active Online — Trendyol Intelligence
        </h1>

        <p class="text-gray-600 mt-3 text-lg">
            نظام تحليل متاجر ومنتجات Trendyol المتقدم
        </p>

    </header>


    <!-- INPUT -->

    <div class="bg-white p-8 rounded-2xl shadow-xl mb-10 no-print">

        <h2 class="text-2xl font-bold text-blue-900 border-b pb-4 mb-6">
            إعداد التحليل
        </h2>


        <div class="grid grid-cols-1 md:grid-cols-3 gap-5 mb-5">

            <div>

                <label class="font-bold text-gray-700">
                    اسم المتجر
                </label>

                <input
                    id="storeNameInput"
                    value="Trendyol Store"
                    class="w-full border-2 rounded-xl px-4 py-3 mt-2"
                >

            </div>


            <div>

                <label class="font-bold text-gray-700">
                    الفئة
                </label>

                <input
                    id="storeCategory"
                    value="Home & Furniture"
                    class="w-full border-2 rounded-xl px-4 py-3 mt-2"
                >

            </div>


            <div>

                <label class="font-bold text-gray-700">
                    الميزانية الإعلانية TL
                </label>

                <input
                    type="number"
                    id="adBudget"
                    value="10000"
                    class="w-full border-2 rounded-xl px-4 py-3 mt-2"
                >

            </div>

        </div>


        <div class="flex gap-4">

            <input
                id="storeUrl"
                class="flex-1 border-2 rounded-xl px-5 py-4"
                placeholder="ضع رابط متجر / صفحة بحث Trendyol"
            >

            <button
                onclick="analyzeStore()"
                id="analyzeBtn"
                class="bg-blue-600 hover:bg-blue-700 text-white px-10 py-4 rounded-xl font-bold"
            >
                🚀 تحليل المتجر
            </button>

        </div>


        <div
            id="loading"
            class="hidden text-center text-blue-600 font-bold mt-6"
        >
            ⏳ جاري تحليل Trendyol واستخراج المنتجات الحقيقية...
        </div>

    </div>


    <!-- RESULTS -->

    <div id="resultContainer" class="hidden">


        <!-- STATISTICS -->

        <div class="grid grid-cols-1 md:grid-cols-5 gap-5 mb-8 no-print">

            <div class="bg-blue-600 text-white p-6 rounded-2xl shadow">
                <p>المنتجات</p>
                <h3 id="statTotal" class="text-3xl font-bold mt-2">0</h3>
            </div>

            <div class="bg-green-600 text-white p-6 rounded-2xl shadow">
                <p>متوسط السعر</p>
                <h3 id="statAvg" class="text-3xl font-bold mt-2">0</h3>
            </div>

            <div class="bg-purple-600 text-white p-6 rounded-2xl shadow">
                <p>أقل سعر</p>
                <h3 id="statMin" class="text-3xl font-bold mt-2">0</h3>
            </div>

            <div class="bg-indigo-600 text-white p-6 rounded-2xl shadow">
                <p>أعلى سعر</p>
                <h3 id="statMax" class="text-3xl font-bold mt-2">0</h3>
            </div>

            <div class="bg-orange-500 text-white p-6 rounded-2xl shadow">
                <p>Opportunity Score</p>
                <h3 id="statScore" class="text-3xl font-bold mt-2">0/100</h3>
            </div>

        </div>


        <!-- CHARTS -->

        <div class="grid grid-cols-1 md:grid-cols-2 gap-8 mb-8 no-print">

            <div class="bg-white p-6 rounded-2xl shadow">

                <h3 class="text-xl font-bold mb-5">
                    📊 توزيع الأسعار
                </h3>

                <div style="height:320px">
                    <canvas id="priceChart"></canvas>
                </div>

            </div>


            <div class="bg-white p-6 rounded-2xl shadow">

                <h3 class="text-xl font-bold mb-5">
                    🎯 مؤشرات المتجر
                </h3>

                <div style="height:320px">
                    <canvas id="scoreChart"></canvas>
                </div>

            </div>

        </div>


        <!-- REPORT -->

        <div
            id="printableReport"
            class="bg-white rounded-2xl shadow-xl p-8 mb-10"
        >

            <div class="flex justify-between items-center border-b pb-5 mb-7">

                <div>

                    <h2 class="text-3xl font-extrabold text-blue-900">
                        التقرير الاستخباراتي الشامل
                    </h2>

                    <p
                        id="storeMeta"
                        class="text-gray-500 mt-2"
                    ></p>

                </div>


                <div class="flex gap-3 no-print">

                    <button
                        onclick="downloadPDF()"
                        class="bg-red-600 text-white px-5 py-3 rounded-xl font-bold"
                    >
                        📥 PDF
                    </button>

                    <button
                        onclick="window.print()"
                        class="bg-green-600 text-white px-5 py-3 rounded-xl font-bold"
                    >
                        🖨️ طباعة
                    </button>

                </div>

            </div>


            <div
                id="reportContent"
                class="report-text bg-gray-50 rounded-xl p-7"
            ></div>

        </div>


        <!-- PRODUCTS -->

        <div class="bg-white rounded-2xl shadow-xl p-8">

            <h2 class="text-2xl font-bold mb-7">
                🔗 المنتجات الحقيقية المستخرجة
            </h2>

            <div
                id="productsGrid"
                class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"
            ></div>

        </div>


    </div>

</div>


<script>

let priceChart = null;
let scoreChart = null;


async function analyzeStore() {

    const storeName =
        document.getElementById("storeNameInput").value;

    const category =
        document.getElementById("storeCategory").value;

    const budget =
        parseFloat(document.getElementById("adBudget").value) || 0;

    const url =
        document.getElementById("storeUrl").value;


    if (!url) {

        alert("ضع رابط Trendyol أولاً");

        return;
    }


    const loading =
        document.getElementById("loading");

    const btn =
        document.getElementById("analyzeBtn");

    const result =
        document.getElementById("resultContainer");


    loading.classList.remove("hidden");

    result.classList.add("hidden");

    btn.disabled = true;


    try {

        const response = await fetch("/api/analyze", {

            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({
                storeName,
                category,
                budget,
                url
            })

        });


        const data = await response.json();


        if (!response.ok) {

            throw new Error(
                data.error || "فشل التحليل"
            );

        }


        const s = data.statistics;


        document.getElementById("statTotal").innerText =
            s.products_collected;

        document.getElementById("statAvg").innerText =
            s.average_price + " TL";

        document.getElementById("statMin").innerText =
            s.min_price + " TL";

        document.getElementById("statMax").innerText =
            s.max_price + " TL";

        document.getElementById("statScore").innerText =
            s.opportunity_score + "/100";


        document.getElementById("storeMeta").innerText =
            `المتجر: ${data.store_info.store_name}
             | الفئة: ${category}
             | المنتجات المحللة: ${s.products_collected}
             | الميزانية: ${budget.toLocaleString()} TL`;


        document.getElementById("reportContent").innerText =
            data.report;


        renderCharts(data.products, s);

        renderProducts(data.products);


        result.classList.remove("hidden");

    }

    catch(error) {

        alert(error.message);

    }

    finally {

        loading.classList.add("hidden");

        btn.disabled = false;

    }

}



function renderProducts(products) {

    const grid =
        document.getElementById("productsGrid");

    grid.innerHTML = "";


    products.forEach((p, index) => {

        const card = document.createElement("div");

        card.className =
            "product-card border rounded-2xl p-5 shadow-sm bg-gray-50";


        card.innerHTML = `

            <img
                src="${escapeHtml(p.image)}"
                class="w-full h-56 object-cover rounded-xl bg-white mb-4"
                onerror="this.style.display='none'"
            >


            <h3 class="font-bold text-gray-900 mb-3">
                ${escapeHtml(p.title)}
            </h3>


            <div class="space-y-2 text-sm">

                <div class="flex justify-between">
                    <span>السعر</span>
                    <strong>${p.price} TL</strong>
                </div>


                <div class="flex justify-between">
                    <span>Opportunity</span>
                    <strong>${p.opportunity_score}/100</strong>
                </div>


                <div class="flex justify-between">
                    <span>التقييم</span>
                    <strong>${p.rating || "غير متاح"}</strong>
                </div>


                <div class="flex justify-between">
                    <span>المراجعات</span>
                    <strong>${p.review_count || "غير متاح"}</strong>
                </div>

            </div>


            <div class="mt-5 space-y-2">


                <a
                    href="${p.url}"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="block bg-green-600 hover:bg-green-700 text-white text-center py-3 rounded-xl font-bold"
                >
                    🔗 فتح المنتج مباشرة
                </a>


                <a
                    href="${p.competitor_url}"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="block bg-indigo-600 hover:bg-indigo-700 text-white text-center py-3 rounded-xl font-bold"
                >
                    ⚡ فتح المنافس
                </a>


            </div>

        `;


        grid.appendChild(card);

    });

}



function escapeHtml(text) {

    if (!text) return "";

    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");

}



function renderCharts(products, stats) {

    if (priceChart)
        priceChart.destroy();

    if (scoreChart)
        scoreChart.destroy();


    priceChart = new Chart(
        document.getElementById("priceChart"),
        {

            type: "bar",

            data: {

                labels:
                    products.map((p, i) => `منتج ${i + 1}`),

                datasets: [{

                    label: "السعر TL",

                    data:
                        products.map(p => p.price)

                }]

            },

            options: {
                responsive: true,
                maintainAspectRatio: false
            }

        }
    );


    scoreChart = new Chart(
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

                    label: "مؤشر المتجر",

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

    const element =
        document.getElementById("printableReport");


    const options = {

        margin: 10,

        filename:
            "ActiveOnline-Trendyol-Intelligence.pdf",

        image: {
            type: "jpeg",
            quality: 0.98
        },

        html2canvas: {
            scale: 2,
            useCORS: true
        },

        jsPDF: {
            unit: "mm",
            format: "a4",
            orientation: "portrait"
        }

    };


    html2pdf()
        .from(element)
        .set(options)
        .save();

}

</script>

</body>
</html>
"""


# ============================================================
# REQUEST HELPERS
# ============================================================

def fetch_page(url):

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=TIMEOUT
    )

    response.raise_for_status()

    return response.text


# ============================================================
# TRENDYOL URL HELPERS
# ============================================================

def is_trendyol_product_url(url):

    if not url:
        return False

    parsed = urlparse(url)

    if "trendyol.com" not in parsed.netloc:
        return False

    path = parsed.path.lower()

    # Trendyol product URLs usually contain -p-123456
    if re.search(r"-p-\d+", path):
        return True

    return False


def extract_product_id(url):

    if not url:
        return None

    match = re.search(
        r"-p-(\d+)",
        urlparse(url).path.lower()
    )

    if match:
        return match.group(1)

    return None


def normalize_product_url(href):

    if not href:
        return None

    href = href.strip()

    absolute = urljoin(
        "https://www.trendyol.com",
        href
    )

    parsed = urlparse(absolute)

    if parsed.netloc and "trendyol.com" not in parsed.netloc:
        return None

    if not is_trendyol_product_url(absolute):
        return None

    product_id = extract_product_id(absolute)

    if not product_id:
        return None

    # Keep the real product path.
    # Remove tracking parameters so we don't accidentally
    # return store/search links.
    clean_url = (
        "https://www.trendyol.com"
        + parsed.path
    )

    return clean_url


# ============================================================
# TEXT / PRICE HELPERS
# ============================================================

def parse_price(text):

    if not text:
        return None

    text = text.replace("\xa0", " ")

    # Turkish formats:
    # 1.299,99
    # 299,99
    # 999 TL

    matches = re.findall(
        r"(\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?)",
        text
    )

    if not matches:
        return None

    values = []

    for value in matches:

        try:

            normalized = value.replace(".", "")
            normalized = normalized.replace(",", ".")

            number = float(normalized)

            if 1 <= number <= 1000000:
                values.append(number)

        except ValueError:
            continue

    if not values:
        return None

    return round(values[0], 2)


def parse_rating(text):

    if not text:
        return None

    matches = re.findall(
        r"([0-5](?:[.,]\d+)?)",
        text
    )

    for value in matches:

        try:

            number = float(
                value.replace(",", ".")
            )

            if 0 <= number <= 5:
                return number

        except:
            pass

    return None


def parse_review_count(text):

    if not text:
        return None

    matches = re.findall(
        r"(\d[\d.]*)",
        text
    )

    numbers = []

    for value in matches:

        try:

            n = int(value.replace(".", ""))

            if n > 0:
                numbers.append(n)

        except:
            pass

    if not numbers:
        return None

    return max(numbers)


# ============================================================
# PRODUCT EXTRACTION
# ============================================================

def extract_products(html):

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    products = []

    seen_ids = set()


    # --------------------------------------------------------
    # Find every anchor containing a real product URL
    # --------------------------------------------------------

    for anchor in soup.find_all("a", href=True):

        href = anchor.get("href")

        product_url = normalize_product_url(href)

        if not product_url:
            continue


        product_id = extract_product_id(
            product_url
        )

        if not product_id:
            continue

        if product_id in seen_ids:
            continue

        seen_ids.add(product_id)


        # ----------------------------------------------------
        # Product title
        # ----------------------------------------------------

        title = (
            anchor.get("title")
            or anchor.get("aria-label")
            or anchor.get_text(" ", strip=True)
        )


        if not title:

            image = anchor.find("img")

            if image:
                title = (
                    image.get("alt")
                    or ""
                )


        title = re.sub(
            r"\s+",
            " ",
            title
        ).strip()


        if not title:
            title = f"Trendyol Product {product_id}"


        # ----------------------------------------------------
        # Image
        # ----------------------------------------------------

        image_url = ""

        image = anchor.find("img")

        if image:

            image_url = (
                image.get("src")
                or image.get("data-src")
                or image.get("data-original")
                or ""
            )


        # ----------------------------------------------------
        # Price
        # ----------------------------------------------------

        container = anchor.parent

        block_text = ""

        if container:
            block_text = container.get_text(
                " ",
                strip=True
            )


        price = parse_price(block_text)


        # ----------------------------------------------------
        # Rating / reviews
        # ----------------------------------------------------

        rating = parse_rating(block_text)

        review_count = parse_review_count(
            block_text
        )


        products.append({

            "id": product_id,

            "title": title[:250],

            "price": price or 0,

            "url": product_url,

            "image": image_url,

            "rating": rating,

            "review_count": review_count,

        })


        if len(products) >= MAX_PRODUCTS:
            break


    return products


# ============================================================
# COMPETITOR SEARCH
# ============================================================

def find_competitor(title):

    words = re.findall(
        r"[A-Za-zÇĞİÖŞÜçğıöşü0-9]+",
        title
    )

    keywords = words[:6]

    query = " ".join(keywords)

    if not query:
        query = "trendyol"


    search_url = (
        "https://www.trendyol.com/sr?q="
        + quote_plus(query)
    )


    try:

        html = fetch_page(
            search_url
        )

        products = extract_products(
            html
        )


        if products:

            return products[0]["url"]

    except:

        pass


    # fallback: search URL,
    # NEVER pretend it is a product URL.

    return search_url


# ============================================================
# ANALYSIS
# ============================================================

def calculate_price_score(products):

    prices = [
        p["price"]
        for p in products
        if p["price"] > 0
    ]

    if len(prices) < 2:
        return 50

    avg = statistics.mean(prices)

    spread = statistics.pstdev(prices)

    if avg == 0:
        return 50

    coefficient = spread / avg

    score = 70 - (coefficient * 60)

    return max(
        0,
        min(100, round(score))
    )


def calculate_seo_score(products):

    if not products:
        return 0

    scores = []

    for p in products:

        title = p["title"]

        length = len(title)

        score = 50


        if 30 <= length <= 120:
            score += 20

        elif 15 <= length < 30:
            score += 5


        words = len(
            title.split()
        )

        if words >= 5:
            score += 20


        if any(
            word in title.lower()
            for word in [
                "kadın",
                "erkek",
                "premium",
                "set",
                "model",
                "yeni"
            ]
        ):
            score += 10


        scores.append(
            min(100, score)
        )


    return round(
        statistics.mean(scores)
    )


def calculate_rating_score(products):

    ratings = [
        p["rating"]
        for p in products
        if p["rating"] is not None
    ]

    if not ratings:
        return 50

    avg = statistics.mean(
        ratings
    )

    return round(
        (avg / 5) * 100
    )


def calculate_review_score(products):

    reviews = [
        p["review_count"]
        for p in products
        if p["review_count"] is not None
    ]

    if not reviews:
        return 50

    avg = statistics.mean(
        reviews
    )

    # logarithmic-ish normalization

    score = min(
        100,
        30 + (avg ** 0.5) * 8
    )

    return round(score)


def calculate_opportunity_score(
    price_score,
    seo_score,
    rating_score,
    review_score
):

    score = (

        price_score * 0.25

        + seo_score * 0.25

        + rating_score * 0.20

        + review_score * 0.30

    )

    return round(score)


def enrich_products(products):

    for p in products:

        score = 50


        # Price signal

        if p["price"] > 0:
            score += 10


        # Title quality

        if len(p["title"]) >= 40:
            score += 10


        # Rating

        if p["rating"]:

            if p["rating"] >= 4.5:
                score += 15

            elif p["rating"] >= 4:
                score += 8


        # Reviews

        if p["review_count"]:

            if p["review_count"] >= 1000:
                score += 15

            elif p["review_count"] >= 100:
                score += 10

            elif p["review_count"] >= 20:
                score += 5


        p["opportunity_score"] = min(
            100,
            score
        )


# ============================================================
# REPORT GENERATOR
# ============================================================

def generate_report(
    store_name,
    category,
    budget,
    products,
    stats
):

    top_products = sorted(
        products,
        key=lambda x: x["opportunity_score"],
        reverse=True
    )[:5]


    estimated_revenue_base = (
        budget * 3
    )

    estimated_revenue_conservative = (
        budget * 2
    )

    estimated_revenue_aggressive = (
        budget * 4
    )


    estimated_orders_base = 0

    if stats["average_price"] > 0:

        estimated_orders_base = int(
            estimated_revenue_base
            / stats["average_price"]
        )


    # --------------------------------------------------------
    # Top products
    # --------------------------------------------------------

    top_lines = []

    for i, p in enumerate(
        top_products,
        start=1
    ):

        top_lines.append(
            f"{i}. {p['title']}\n"
            f"   السعر: {p['price']} TL\n"
            f"   Opportunity Score: "
            f"{p['opportunity_score']}/100\n"
            f"   الرابط المباشر: {p['url']}\n"
        )


    top_text = "\n".join(
        top_lines
    )


    # --------------------------------------------------------
    # Budget
    # --------------------------------------------------------

    meta_budget = round(
        budget * 0.40,
        2
    )

    google_budget = round(
        budget * 0.25,
        2
    )

    trendyol_budget = round(
        budget * 0.25,
        2
    )

    retargeting_budget = round(
        budget * 0.10,
        2
    )


    report = f"""

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 ACTIVE ONLINE — TRENDYOL INTELLIGENCE
التقرير الاستخباراتي الشامل
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🏪 المتجر:
{store_name}

📂 الفئة:
{category}

📦 المنتجات التي تم تحليلها:
{stats['products_collected']}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. الملخص التنفيذي
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

تم تحليل {stats['products_collected']} منتجاً حقيقياً تم استخراج روابطها من صفحات Trendyol.

متوسط السعر:
{stats['average_price']} TL

أقل سعر:
{stats['min_price']} TL

أعلى سعر:
{stats['max_price']} TL

مؤشر فرصة المتجر:
{stats['opportunity_score']}/100

التقييم العام مبني على:
• هيكل الأسعار
• جودة عناوين المنتجات
• التقييمات
• حجم المراجعات
• قابلية المنتجات للتسويق


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2. تحليل هيكل الأسعار
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

أقل سعر: {stats['min_price']} TL
متوسط السعر: {stats['average_price']} TL
أعلى سعر: {stats['max_price']} TL

تحليل الأسعار:

• المنتجات منخفضة السعر يمكن استخدامها لجذب العملاء.
• المنتجات المتوسطة مناسبة لبناء حجم مبيعات.
• المنتجات الأعلى سعراً تحتاج إلى Creative أقوى وإثبات قيمة واضح.
• يجب تجنب الاعتماد على الخصم فقط كوسيلة للبيع.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
3. تحليل SEO وعناوين المنتجات
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SEO Score:
{stats['seo_score']}/100

التوصيات:

• وضع أهم Keyword في بداية العنوان.
• استخدام اللغة التركية التي يبحث بها العميل.
• عدم تكرار الكلمات بدون فائدة.
• توضيح النوع والمقاس والخامة والاستخدام عند توفرها.
• استخدام عنوان واضح وقابل للقراءة على الهاتف.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
4. تحليل التقييمات والمراجعات
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Rating Score:
{stats['rating_score']}/100

Review Score:
{stats['review_score']}/100

التقييم المرتفع مع عدد مراجعات كبير يمثل Social Proof قوياً.

المنتجات التي لديها تقييمات جيدة ومراجعات كثيرة يجب إعطاؤها أولوية في الحملات.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
5. أفضل المنتجات المرشحة للنمو
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{top_text}


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
6. استراتيجية الإعلانات
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

الميزانية الشهرية:
{budget:,.2f} TL

التوزيع المقترح:

Meta Ads:
{meta_budget:,.2f} TL

Google Ads:
{google_budget:,.2f} TL

Trendyol Ads:
{trendyol_budget:,.2f} TL

Retargeting:
{retargeting_budget:,.2f} TL


الاستراتيجية:

1. اختبار عدد محدود من المنتجات.
2. إيقاف المنتجات ذات النتائج الضعيفة.
3. رفع الميزانية تدريجياً للمنتجات الرابحة.
4. إعادة استهداف الزوار.
5. إنشاء Creative مختلف لكل Product Angle.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
7. السيناريو المالي — تقديري
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ هذه الأرقام تقديرية وليست بيانات مبيعات فعلية.

Scenario Conservative:
ROAS افتراضي = 2x

Revenue:
{estimated_revenue_conservative:,.2f} TL


Scenario Base:
ROAS افتراضي = 3x

Revenue:
{estimated_revenue_base:,.2f} TL

طلبات تقديرية:
{estimated_orders_base}


Scenario Aggressive:
ROAS افتراضي = 4x

Revenue:
{estimated_revenue_aggressive:,.2f} TL


مهم:
الـ ROAS الحقيقي يجب حسابه من بيانات الإعلانات والمبيعات الفعلية.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
8. استراتيجية المنافسة
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

يجب مراقبة:

• السعر
• التقييم
• عدد المراجعات
• الصور
• العنوان
• العروض
• الشحن
• البائع
• ترتيب المنتج
• نقاط القوة في وصف المنتج


لا ننصح بمحاولة منافسة كل المنتجات.

الأفضل اختيار 5–10 منتجات رئيسية وبناء استراتيجية
مركزة حولها.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
9. خطة تحسين المنتجات
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Priority 1:
تحسين المنتجات ذات Opportunity Score مرتفع.

Priority 2:
تحسين الصور والعناوين.

Priority 3:
اختبار أسعار وعروض مختلفة.

Priority 4:
تشغيل إعلانات على المنتجات التي لديها Social Proof.

Priority 5:
إعادة استهداف العملاء والزوار.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
10. خطة 30 يوم
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

الأسبوع الأول:
• تحليل المنافسين.
• تحسين العناوين.
• تحسين الصور.
• تحديد المنتجات المرشحة.
• تجهيز Tracking.

الأسبوع الثاني:
• إطلاق حملات اختبار.
• اختبار أكثر من Creative.
• قياس CTR و CPC و Add-to-Cart.

الأسبوع الثالث:
• إيقاف الإعلانات الضعيفة.
• رفع ميزانية المنتجات الرابحة.
• إطلاق Retargeting.

الأسبوع الرابع:
• تحليل ROAS الحقيقي.
• تحليل المنتجات الأعلى ربحية.
• تجهيز عروض الشهر القادم.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
11. المخاطر
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ ارتفاع تكلفة الإعلانات.

⚠️ منافسة سعرية قوية.

⚠️ ضعف الصور أو العناوين.

⚠️ الاعتماد على Product واحد.

⚠️ ارتفاع الإلغاء أو المرتجعات.

⚠️ انخفاض التقييمات.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
12. التوصية النهائية
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Opportunity Score:
{stats['opportunity_score']}/100

التوصية:

التركيز على المنتجات ذات أعلى Opportunity Score،
تحسين SEO والصور أولاً، ثم اختبار الإعلانات بميزانية
محدودة، وبعد ظهور بيانات فعلية يتم Scale للمنتجات الرابحة.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Active Online
Trendyol Intelligence
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""


    return report


# ============================================================
# API
# ============================================================

@app.route("/")
def home():

    return render_template_string(
        HTML_TEMPLATE
    )


@app.route(
    "/api/analyze",
    methods=["POST"]
)
def analyze():

    try:

        data = request.get_json(
            silent=True
        ) or {}


        store_name = str(
            data.get(
                "storeName",
                "Trendyol Store"
            )
        ).strip()


        category = str(
            data.get(
                "category",
                "عام"
            )
        ).strip()


        budget = float(
            data.get(
                "budget",
                10000
            )
        )


        url = str(
            data.get(
                "url",
                ""
            )
        ).strip()


        if not url:

            return jsonify({
                "error":
                "يجب إدخال رابط Trendyol"
            }), 400


        # ----------------------------------------------------
        # Fetch real Trendyol page
        # ----------------------------------------------------

        html = fetch_page(
            url
        )


        # ----------------------------------------------------
        # Extract real products
        # ----------------------------------------------------

        products = extract_products(
            html
        )


        if not products:

            return jsonify({

                "error":
                "لم يتم العثور على منتجات حقيقية في الصفحة. "
                "تأكد من أن الرابط صفحة Trendyol صحيحة وأن الصفحة "
                "متاحة للقراءة."

            }), 422


        # ----------------------------------------------------
        # Limit products
        # ----------------------------------------------------

        products = products[
            :MAX_PRODUCTS
        ]


        # ----------------------------------------------------
        # Competitors
        # ----------------------------------------------------

        for product in products:

            product[
                "competitor_url"
            ] = find_competitor(
                product["title"]
            )


        # ----------------------------------------------------
        # Product enrichment
        # ----------------------------------------------------

        enrich_products(
            products
        )


        # ----------------------------------------------------
        # Statistics
        # ----------------------------------------------------

        prices = [
            p["price"]
            for p in products
            if p["price"] > 0
        ]


        if not prices:

            return jsonify({
                "error":
                "تم العثور على المنتجات ولكن لم نستطع "
                "استخراج الأسعار."
            }), 422


        avg_price = round(
            statistics.mean(prices),
            2
        )


        price_score = (
            calculate_price_score(
                products
            )
        )


        seo_score = (
            calculate_seo_score(
                products
            )
        )


        rating_score = (
            calculate_rating_score(
                products
            )
        )


        review_score = (
            calculate_review_score(
                products
            )
        )


        opportunity_score = (
            calculate_opportunity_score(

                price_score,

                seo_score,

                rating_score,

                review_score

            )
        )


        stats = {

            "products_collected":
                len(products),

            "min_price":
                round(min(prices), 2),

            "max_price":
                round(max(prices), 2),

            "average_price":
                avg_price,

            "price_score":
                price_score,

            "seo_score":
                seo_score,

            "rating_score":
                rating_score,

            "review_score":
                review_score,

            "opportunity_score":
                opportunity_score

        }


        # ----------------------------------------------------
        # Report
        # ----------------------------------------------------

        report = generate_report(

            store_name,

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
                    store_name,

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


    except requests.exceptions.RequestException as e:

        return jsonify({

            "error":
                "تعذر الوصول إلى Trendyol حالياً: "
                + str(e)

        }), 502


    except Exception as e:

        return jsonify({

            "error":
                "حدث خطأ أثناء التحليل: "
                + str(e)

        }), 500


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
