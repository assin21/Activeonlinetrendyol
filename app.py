       import os
import re
import json
import time
import statistics
from urllib.parse import urljoin, quote_plus

import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template_string, request, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

MAX_PRODUCTS = int(os.getenv("MAX_PRODUCTS", "40"))
MAX_PRODUCT_PAGES = int(os.getenv("MAX_PRODUCT_PAGES", "25"))

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.trendyol.com/",
})

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>Active Online — Trendyol Marketing Intelligence</title>
    <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        @media print {
            body * { visibility: hidden; }
            #printableReport, #printableReport * { visibility: visible; }
            #printableReport { position: absolute; left: 0; top: 0; width: 100%; }
            .no-print { display: none; }
        }
    </style>
</head>
<body class="bg-gray-50 text-gray-900 font-sans">
    <div class="container mx-auto px-4 py-10 max-w-6xl">
        <header class="mb-8 text-center no-print">
            <h1 class="text-3xl font-bold text-blue-900">Active Online — Trendyol Marketing Intelligence</h1>
            <p class="text-gray-600 mt-2">منصة ذكاء الأعمال، تحليل الأسعار التنافسية، ووضع الخطط التسويقية الشاملة لمتاجر ترينديول</p>
        </header>

        <div class="bg-white p-6 rounded-xl shadow-md mb-8 border border-gray-100 no-print">
            <h2 class="text-xl font-semibold mb-4 text-blue-800">تحليل متجر عميق وخطة تسويقية استراتيجية متكاملة</h2>
            <div class="flex flex-col md:flex-row gap-4">
                <input type="text" id="storeUrl" placeholder="أدخل رابط متجر Trendyol أو معرف البائع (Merchant ID)..." 
                       class="flex-1 border border-gray-300 rounded-lg px-4 py-3 focus:outline-none focus:border-blue-600 text-left" dir="ltr">
                <button onclick="analyzeStore()" id="analyzeBtn" class="bg-blue-600 text-white px-8 py-3 rounded-lg font-bold hover:bg-blue-700 transition shadow">
                    بدء التحليل والخطة التسويقية
                </button>
            </div>
            <div id="loading" class="mt-4 hidden text-blue-600 font-medium text-center">جاري سحب بيانات المنتجات، تحليل أسعار المنافسين، وصياغة الخطة التسويقية الاستراتيجية المتقدمة... يرجى الانتظار</div>
        </div>

        <div id="resultContainer" class="hidden space-y-8">
            <div class="bg-white p-6 rounded-xl shadow-md border border-gray-100 no-print">
                <h3 class="text-xl font-bold mb-4 text-gray-800 border-b pb-2">ملخص بيانات المتجر الإحصائية</h3>
                <div id="storeDetails" class="grid grid-cols-2 md:grid-cols-4 gap-4 bg-blue-50 p-4 rounded-lg text-sm"></div>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-6 no-print">
                <div class="bg-white p-6 rounded-xl shadow-md border border-gray-100 flex flex-col items-center">
                    <h3 class="text-lg font-bold mb-4 text-gray-800 border-b pb-2 w-full text-center">مخطط الأسعار (أدنى، متوسط، أقصى)</h3>
                    <div class="w-full h-64 flex justify-center items-center">
                        <canvas id="priceChart"></canvas>
                    </div>
                </div>
                <div class="bg-white p-6 rounded-xl shadow-md border border-gray-100 flex flex-col items-center">
                    <h3 class="text-lg font-bold mb-4 text-gray-800 border-b pb-2 w-full text-center">توزيع المنتجات والتسعير</h3>
                    <div class="w-full h-64 flex justify-center items-center">
                        <canvas id="discountChart"></canvas>
                    </div>
                </div>
            </div>

            <div id="printableReport" class="bg-white p-6 rounded-xl shadow-md border border-gray-100">
                <div class="flex justify-between items-center border-b pb-2 mb-4">
                    <h3 class="text-xl font-bold text-gray-800">التقرير الاستخباراتي والخطة التسويقية الشاملة</h3>
                    <button onclick="window.print()" class="no-print bg-green-600 text-white px-4 py-2 rounded-lg text-sm font-bold hover:bg-green-700 transition shadow flex items-center gap-2">
                        🖨️ طباعة أو تصدير التقرير (PDF)
                    </button>
                </div>
                <div id="reportContent" class="whitespace-pre-wrap bg-gray-50 p-6 rounded-lg text-gray-800 text-sm leading-loose border shadow-inner" dir="auto"></div>
            </div>

            <div class="bg-white p-6 rounded-xl shadow-md border border-gray-100 no-print">
                <h3 class="text-xl font-bold mb-4 text-gray-800 border-b pb-2">عينة من منتجات المتجر مع روابط المنافسين وأقل الأسعار بالسوق</h3>
                <div id="productsGrid" class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6"></div>
            </div>
        </div>
    </div>

    <script>
        let priceChartInstance = null;
        let discountChartInstance = null;

        async function analyzeStore() {
            const url = document.getElementById('storeUrl').value;
            if (!url) return alert('الرجاء إدخال رابط صالح');
            
            const loading = document.getElementById('loading');
            const resultContainer = document.getElementById('resultContainer');
            const btn = document.getElementById('analyzeBtn');
            
            loading.classList.remove('hidden');
            resultContainer.classList.add('hidden');
            btn.disabled = true;
            
            try {
                const response = await fetch('/api/analyze', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url })
                });
                
                const data = await response.json();
                loading.classList.add('hidden');
                btn.disabled = false;
                
                if (response.ok) {
                    const stats = data.statistics;
                    document.getElementById('storeDetails').innerHTML = `
                        <div><strong>اسم المتجر:</strong> ${data.store_info.store_name || 'غير متوفر'}</div>
                        <div><strong>معرف البائع:</strong> ${data.store_info.merchant_id || 'غير متوفر'}</div>
                        <div><strong>المنتجات المجمعة:</strong> ${stats.products_collected}</div>
                        <div><strong>متوسط الأسعار:</strong> ${stats.average_price ? stats.average_price + ' TL' : 'غير متوفر'}</div>
                    `;
                    document.getElementById('reportContent').innerText = data.report;
                    
                    renderCharts(stats);

                    const grid = document.getElementById('productsGrid');
                    grid.innerHTML = '';
                    if (data.products && data.products.length > 0) {
                        data.products.forEach(p => {
                            const imgUrl = (p.images && p.images.length > 0) ? p.images[0] : 'https://via.placeholder.com/150';
                            
                            const comp1Price = p.competitor_1_price ? p.competitor_1_price + ' TL' : 'غير متوفر';
                            const comp1Link = p.competitor_1_url ? `<a href="${p.competitor_1_url}" target="_blank" class="text-blue-600 underline font-semibold">رابط المنافس الأول</a>` : 'غير متوفر';
                            
                            const comp2Price = p.competitor_2_price ? p.competitor_2_price + ' TL' : 'غير متوفر';
                            const comp2Link = p.competitor_2_url ? `<a href="${p.competitor_2_url}" target="_blank" class="text-blue-600 underline font-semibold">رابط المنافس الثاني</a>` : 'غير متوفر';

                            const card = `
                                <div class="border rounded-lg p-3 shadow-sm bg-gray-50 flex flex-col justify-between">
                                    <div>
                                        <img src="${imgUrl}" alt="Product Image" class="w-full h-48 object-cover rounded-md mb-2 bg-white" onerror="this.src='https://via.placeholder.com/150'">
                                        <h4 class="font-semibold text-xs text-gray-800 line-clamp-2 mb-1" title="${p.title || ''}">${p.title || 'منتج بدون عنوان'}</h4>
                                    </div>
                                    <div class="mt-2 pt-2 border-t text-xs space-y-1.5">
                                        <div class="flex justify-between bg-blue-50 p-1 rounded"><span class="font-bold text-blue-900">سعر متجرك:</span> <span class="text-blue-700 font-bold">${p.price ? p.price + ' TL' : 'غير متوفر'}</span></div>
                                        
                                        <div class="flex justify-between items-center text-gray-700">
                                            <span>المنافس 1 (${comp1Price}):</span>
                                            <span>${comp1Link}</span>
                                        </div>
                                        
                                        <div class="flex justify-between items-center text-gray-700">
                                            <span>المنافس 2 (${comp2Price}):</span>
                                            <span>${comp2Link}</span>
                                        </div>

                                        <div class="pt-2 text-center">
                                            <a href="${p.url}" target="_blank" class="block w-full bg-green-600 hover:bg-green-700 text-white py-1.5 px-3 rounded text-center font-medium transition shadow-sm">
                                                🔗 رابط منتجك الأصلي
                                            </a>
                                        </div>
                                    </div>
                                </div>
                            `;
                            grid.innerHTML += card;
                        });
                    } else {
                        grid.innerHTML = '<p class="text-gray-500 col-span-full text-center">لم يتم العثور على منتجات متاحة للعرض.</p>';
                    }

                    resultContainer.classList.remove('hidden');
                } else {
                    alert('خطأ: ' + (data.error || 'حدث خطأ غير متوقع'));
                }
            } catch (err) {
                loading.classList.add('hidden');
                btn.disabled = false;
                alert('حدث خطأ في الاتصال بالسيرفر');
            }
        }

        function renderCharts(stats) {
            if (priceChartInstance) priceChartInstance.destroy();
            if (discountChartInstance) discountChartInstance.destroy();

            const ctxPrice = document.getElementById('priceChart').getContext('2d');
            priceChartInstance = new Chart(ctxPrice, {
                type: 'bar',
                data: {
                    labels: ['أقل سعر', 'متوسط الأسعار', 'أعلى سعر'],
                    datasets: [{
                        label: 'السعر بـ TL',
                        data: [stats.min_price || 0, stats.average_price || 0, stats.max_price || 0],
                        backgroundColor: ['rgba(54, 162, 235, 0.6)', 'rgba(75, 192, 192, 0.6)', 'rgba(255, 99, 132, 0.6)'],
                        borderColor: ['rgba(54, 162, 235, 1)', 'rgba(75, 192, 192, 1)', 'rgba(255, 99, 132, 1)'],
                        borderWidth: 1
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false, scales: { y: { beginAtZero: true } } }
            });

            const ctxDiscount = document.getElementById('discountChart').getContext('2d');
            discountChartInstance = new Chart(ctxDiscount, {
                type: 'doughnut',
                data: {
                    labels: ['منتجات بمستوى تسعير تنافسي', 'منتجات بحاجة لمراجعة سعرية'],
                    datasets: [{
                        data: [stats.prices_available || 0, 5],
                        backgroundColor: ['rgba(75, 192, 192, 0.7)', 'rgba(255, 159, 64, 0.7)']
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false }
            });
        }
    </script>
</body>
</html>
"""

def clean_text(value):
    if value is None:
        return None
    return re.sub(r"\s+", " ", str(value)).strip() or None

def extract_merchant_id(url):
    m = re.search(r"m-(\d+)", url)
    if m:
        return m.group(1)
    digits = re.findall(r"\d+", url)
    for d in digits:
        if len(d) >= 5:
            return d
    return "222222"

def fetch_via_api(merchant_id):
    api_url = f"https://apigw.trendyol.com/discovery-web-searchgw-service/v2/api/filter/by-merchant?merchantId={merchant_id}&pi=1&ps={MAX_PRODUCTS}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.trendyol.com",
        "Referer": f"https://www.trendyol.com/butik/liste/-m-{merchant_id}"
    }
    try:
        r = requests.get(api_url, headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            return data.get("result", {}).get("products", [])
    except Exception:
        pass
    return []

def fetch_competitors(product_title):
    if not product_title:
        return None, None, None, None
    words = re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü0-9]+", product_title)
    q = " ".join(words[:5])
    if len(q) < 4:
        return None, None, None, None
    search_url = f"https://apigw.trendyol.com/discovery-web-searchgw-service/v2/api/search?q={quote_plus(q)}&pi=1"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Origin": "https://www.trendyol.com",
        "Referer": "https://www.trendyol.com/"
    }
    try:
        r = requests.get(search_url, headers=headers, timeout=10)
        if r.status_code == 200:
            items = r.json().get("result", {}).get("products", [])
            comps = []
            for item in items:
                p_url = "https://www.trendyol.com" + item.get("url", "")
                p_price = item.get("price", {}).get("sellingPrice", {}).get("value")
                if p_url and p_price:
                    comps.append({"url": p_url, "price": float(p_price)})
            comps = sorted(comps, key=lambda x: x["price"])
            c1 = comps[0] if len(comps) > 0 else {}
            c2 = comps[1] if len(comps) > 1 else {}
            return c1.get("url"), c1.get("price"), c2.get("url"), c2.get("price")
    except Exception:
        pass
    return None, None, None, None

def collect_store_data(url):
    merchant_id = extract_merchant_id(url)
    raw_products = fetch_via_api(merchant_id)
    
    products = []
    for item in raw_products[:MAX_PRODUCT_PAGES]:
        title = item.get("name")
        images = ["https://cdn.dsmcdn.com/" + img for img in item.get("images", [])]
        p_url = "https://www.trendyol.com" + item.get("url", "")
        price_info = item.get("price", {}).get("sellingPrice", {})
        price = price_info.get("value")
        
        rating_info = item.get("ratingScore", {})
        rating = rating_info.get("averageRating")
        review_count = rating_info.get("totalReviewCount")

        c1_u, c1_p, c2_u, c2_p = fetch_competitors(title)

        products.append({
            "url": p_url,
            "title": title,
            "brand": item.get("brand", {}).get("name"),
            "price": float(price) if price else None,
            "currency": "TRY",
            "rating": float(rating) if rating else None,
            "review_count": int(review_count) if review_count else None,
            "images": images,
            "competitor_1_url": c1_u,
            "competitor_1_price": c1_p,
            "competitor_2_url": c2_u,
            "competitor_2_price": c2_p,
        })

    store_info = {
        "store_name": raw_products[0].get("merchantName", "Trendyol Store") if raw_products else "Store",
        "merchant_id": merchant_id,
        "store_url": url,
        "rating": None,
        "review_count": None,
    }
    return store_info, products

def calculate_stats(products):
    prices = [p["price"] for p in products if p.get("price") is not None]
    ratings = [p["rating"] for p in products if p.get("rating") is not None]
    reviews = [p["review_count"] for p in products if p.get("review_count") is not None]

    return {
        "products_collected": len(products),
        "prices_available": len(prices),
        "min_price": round(min(prices), 2) if prices else None,
        "max_price": round(max(prices), 2) if prices else None,
        "average_price": round(statistics.mean(prices), 2) if prices else None,
        "median_price": round(statistics.median(prices), 2) if prices else None,
        "average_product_rating": round(statistics.mean(ratings), 2) if ratings else None,
        "total_product_reviews": sum(reviews) if reviews else None,
        "products_with_reviews": len(reviews),
    }

def make_ai_report(payload):
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY غير موجود في ملف .env")

    gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    
    system = "أنت Active Online Intelligence، محلل تجارة إلكترونية ومستشار تسويق رقمي محترف متخصص في منصة Trendyol والسوق التركي."
    prompt = f"""
{system}
قم بتحليل متجر Trendyol التالي بناءً على البيانات الفعلية المستخرجة (بما في ذلك مقارنة الأسعار مع أرخص المنافسين في السوق):

DATA:
{json.dumps(payload, ensure_ascii=False, indent=2)}

أريد تقريراً استخباراتياً وخطة تسويقية متكاملة واحترافية باللغة العربية، بحيث تكون غنية بالتفاصيل والأفكار الإبداعية وتغطي الأقسام التالية:

1. **الملخص التنفيذي وأداء المتجر (Executive Summary)**
2. **تحليل المحفظة المنتجات والتسعير التنافسي (Product & Price Benchmarking)** مقارنة بالمنافسين الحقيقيين في السوق.
3. **استراتيجية التسويق الرقمي وإعلانات الأداء (Performance Marketing & Meta/Google Ads)** (كيفية استهداف الجمهور التركي، بناء قمع المبيعات Funnels، وأفضل الكلمات المفتاحية).
4. **استراتيجيات زيادة معدل التحويل (CRO) ومتوسط قيمة السلة (AOV)** (أفكار للـ Bundles، العروض المشتركة، وتقليل التخلي عن السلة).
5. **أفكار إبداعية إضافية ومبتكرة (Growth Hacking & Innovative Ideas)** (مثل التسويق عبر المؤثرين Micro-influencers في تركيا، استغلال مواسم الخصومات الكبرى في ترينديول، وبرامج ولاء العملاء).
6. **خطة العمل التسويقية للـ 30 يوماً القادمة (30-Day Marketing Action Plan)** منقسمة لأربع أسابيع واضحة وقابلة للتنفيذ.
7. **التوصيات الاستراتيجية النهائية (Final Strategic Recommendations)**
"""
    payload_body = {"contents": [{"parts": [{"text": prompt}]}]}
    response = requests.post(gemini_url, json=payload_body, timeout=60)
    if response.status_code == 200:
        return response.json()['candidates'][0]['content']['parts'][0]['text']
    else:
        raise RuntimeError(f"خطأ من خادم جوجل: {response.text}")

def analyze(url):
    started = time.time()
    store_info, products = collect_store_data(url)
    stats = calculate_stats(products)

    payload = {
        "store": store_info,
        "statistics": stats,
        "products": products,
        "meta": {"collection_time_seconds": round(time.time() - started, 2)},
    }
    report = make_ai_report(payload)
    return {
        "status": "success",
        "store_info": store_info,
        "statistics": stats,
        "products": products,
        "competitors": [],
        "report": report,
        "meta": payload["meta"],
    }

@app.route("/")
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    data = request.get_json(silent=True) or {}
    url = clean_text(data.get("url"))
    if not url:
        return jsonify({"error": "الرابط مطلوب"}), 400
    try:
        result = analyze(url)
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
