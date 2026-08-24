import os
import re
import json
import time
import statistics
from urllib.parse import quote_plus

import requests
from flask import Flask, render_template_string, request, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

MAX_PRODUCTS = 12  # تقليل العدد لضمان السرعة الفائقة وعدم حدوث Timeout

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>Active Online — Trendyol Marketing Intelligence</title>
    <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body class="bg-gray-50 text-gray-900 font-sans">
    <div class="container mx-auto px-4 py-10 max-w-6xl">
        <header class="mb-8 text-center">
            <h1 class="text-3xl font-bold text-blue-900">Active Online — Trendyol Marketing Intelligence</h1>
            <p class="text-gray-600 mt-2">منصة ذكاء الأعمال، تحليل الأسعار التنافسية، ووضع الخطط التسويقية الشاملة لمتاجر ترينديول</p>
        </header>

        <div class="bg-white p-6 rounded-xl shadow-md mb-8 border border-gray-100">
            <h2 class="text-xl font-semibold mb-4 text-blue-800">تحليل متجر عميق وخطة تسويقية استراتيجية متكاملة</h2>
            <div class="flex flex-col md:flex-row gap-4">
                <input type="text" id="storeUrl" placeholder="أدخل رابط متجر Trendyol أو معرف البائع (Merchant ID)..." 
                       class="flex-1 border border-gray-300 rounded-lg px-4 py-3 focus:outline-none focus:border-blue-600 text-left" dir="ltr">
                <button onclick="analyzeStore()" id="analyzeBtn" class="bg-blue-600 text-white px-8 py-3 rounded-lg font-bold hover:bg-blue-700 transition shadow">
                    بدء التحليل والخطة التسويقية
                </button>
            </div>
            <div id="loading" class="mt-4 hidden text-blue-600 font-medium text-center">جاري سحب بيانات المنتجات وصياغة الخطة التسويقية الاستراتيجية... يرجى الانتظار</div>
        </div>

        <div id="resultContainer" class="hidden space-y-8">
            <div class="bg-white p-6 rounded-xl shadow-md border border-gray-100">
                <h3 class="text-xl font-bold mb-4 text-gray-800 border-b pb-2">ملخص بيانات المتجر الإحصائية</h3>
                <div id="storeDetails" class="grid grid-cols-2 md:grid-cols-4 gap-4 bg-blue-50 p-4 rounded-lg text-sm"></div>
            </div>

            <div class="bg-white p-6 rounded-xl shadow-md border border-gray-100">
                <div class="flex justify-between items-center border-b pb-2 mb-4">
                    <h3 class="text-xl font-bold text-gray-800">التقرير الاستخباراتي والخطة التسويقية الشاملة</h3>
                    <button onclick="window.print()" class="bg-green-600 text-white px-4 py-2 rounded-lg text-sm font-bold hover:bg-green-700 transition shadow">
                        🖨️ طباعة أو تصدير التقرير (PDF)
                    </button>
                </div>
                <div id="reportContent" class="whitespace-pre-wrap bg-gray-50 p-6 rounded-lg text-gray-800 text-sm leading-loose border shadow-inner" dir="auto"></div>
            </div>

            <div class="bg-white p-6 rounded-xl shadow-md border border-gray-100">
                <h3 class="text-xl font-bold mb-4 text-gray-800 border-b pb-2">عينة من منتجات المتجر</h3>
                <div id="productsGrid" class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6"></div>
            </div>
        </div>
    </div>

    <script>
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

                    const grid = document.getElementById('productsGrid');
                    grid.innerHTML = '';
                    if (data.products && data.products.length > 0) {
                        data.products.forEach(p => {
                            const imgUrl = (p.images && p.images.length > 0) ? p.images[0] : 'https://via.placeholder.com/150';
                            const card = `
                                <div class="border rounded-lg p-3 shadow-sm bg-gray-50 flex flex-col justify-between">
                                    <div>
                                        <img src="${imgUrl}" alt="Product" class="w-full h-48 object-cover rounded-md mb-2 bg-white">
                                        <h4 class="font-semibold text-xs text-gray-800 line-clamp-2 mb-1">${p.title || 'منتج بدون عنوان'}</h4>
                                    </div>
                                    <div class="mt-2 pt-2 border-t text-xs space-y-1.5">
                                        <div class="flex justify-between bg-blue-50 p-1 rounded"><span class="font-bold text-blue-900">السعر:</span> <span class="text-blue-700 font-bold">${p.price ? p.price + ' TL' : 'غير متوفر'}</span></div>
                                        <a href="${p.url}" target="_blank" class="block w-full bg-green-600 text-white py-1.5 px-3 rounded text-center font-medium shadow-sm">🔗 رابط المنتج</a>
                                    </div>
                                </div>
                            `;
                            grid.innerHTML += card;
                        });
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
        r = requests.get(api_url, headers=headers, timeout=10)
        if r.status_code == 200:
            return r.json().get("result", {}).get("products", [])
    except Exception:
        pass
    return []

def collect_store_data(url):
    merchant_id = extract_merchant_id(url)
    raw_products = fetch_via_api(merchant_id)
    
    products = []
    for item in raw_products:
        title = item.get("name")
        images = ["https://cdn.dsmcdn.com/" + img for img in item.get("images", [])]
        p_url = "https://www.trendyol.com" + item.get("url", "")
        price_info = item.get("price", {}).get("sellingPrice", {})
        price = price_info.get("value")
        
        products.append({
            "url": p_url,
            "title": title,
            "price": float(price) if price else None,
            "images": images,
        })

    store_info = {
        "store_name": raw_products[0].get("merchantName", "Trendyol Store") if raw_products else "Store",
        "merchant_id": merchant_id,
        "store_url": url,
    }
    return store_info, products

def calculate_stats(products):
    prices = [p["price"] for p in products if p.get("price") is not None]
    return {
        "products_collected": len(products),
        "min_price": round(min(prices), 2) if prices else None,
        "max_price": round(max(prices), 2) if prices else None,
        "average_price": round(statistics.mean(prices), 2) if prices else None,
    }

def make_ai_report(payload):
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY غير موجود")

    gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    
    system = "أنت مستشار تسويق رقمي محترف متخصص في منصة Trendyol والسوق التركي."
    prompt = f"""
{system}
قم بتحليل بيانات متجر ترينديول التالي لصياغة خطة تسويقية استراتيجية متكاملة واحترافية باللغة العربية:

DATA:
{json.dumps(payload, ensure_ascii=False, indent=2)}

أريد تقريراً استخباراتياً يغطي الأقسام التالية بالتفصيل:
1. الملخص التنفيذي وتحليل الأسعار
2. استراتيجية التسويق الرقمي وإعلانات الأداء (Meta & Google Ads)
3. استراتيجيات رفع معدل التحويل (CRO) ومتوسط قيمة السلة (AOV)
4. أفكار تسويقية مبتكرةGrowth Hacking (مثل المؤثرين المواسم)
5. خطة عمل تسويقية للـ 30 يوماً القادمة
"""
    payload_body = {"contents": [{"parts": [{"text": prompt}]}]}
    response = requests.post(gemini_url, json=payload_body, timeout=30)
    if response.status_code == 200:
        return response.json()['candidates'][0]['content']['parts'][0]['text']
    else:
        raise RuntimeError("خطأ في الاتصال بخادم الذكاء الاصطناعي")

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
        store_info, products = collect_store_data(url)
        stats = calculate_stats(products)
        payload = {"store": store_info, "statistics": stats, "products": products}
        report = make_ai_report(payload)
        return jsonify({
            "status": "success",
            "store_info": store_info,
            "statistics": stats,
            "products": products,
            "report": report
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
