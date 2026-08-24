import re
import statistics
from urllib.parse import urljoin, urlparse
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
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

HTML = """
<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Active Online — Trendyol Intelligence</title>
<style>
body{font-family:Arial,sans-serif;background:#f3f4f6;margin:0;color:#172033}
.wrap{max-width:1100px;margin:30px auto;padding:20px}
.card{background:#fff;border-radius:16px;padding:24px;margin-bottom:20px;box-shadow:0 4px 18px #0001}
input,textarea{width:100%;box-sizing:border-box;padding:13px;border:1px solid #ddd;border-radius:10px;margin:7px 0 15px}
button{background:#155eef;color:#fff;border:0;border-radius:10px;padding:13px 22px;font-weight:bold;cursor:pointer}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px}
.stat{color:#fff;border-radius:14px;padding:18px;background:#155eef}
.product{border:1px solid #e5e7eb;border-radius:14px;padding:16px}
.product img{width:100%;height:190px;object-fit:cover;border-radius:10px}
.error{background:#fee2e2;color:#991b1b;padding:15px;border-radius:10px;margin-top:15px}
.warn{background:#fef3c7;color:#92400e;padding:15px;border-radius:10px;margin-top:15px}
pre{white-space:pre-wrap;line-height:1.9;background:#f8fafc;padding:20px;border-radius:12px}
a{color:#155eef;text-decoration:none;font-weight:bold}
.hidden{display:none}
</style>
</head>
<body>
<div class="wrap">
<div class="card">
<h1>Active Online — Trendyol Intelligence</h1>
<p>تحليل متجر ومنتجات Trendyol</p>

<label>اسم المتجر</label>
<input id="storeName" value="Trendyol Store">

<label>الفئة</label>
<input id="category" value="Home & Furniture">

<label>الميزانية TL</label>
<input id="budget" type="number" value="10000">

<label>رابط المتجر / صفحة Trendyol</label>
<input id="url" placeholder="https://www.trendyol.com/magaza/...">

<button onclick="analyze()">تحليل المتجر</button>

<div id="error" class="error hidden"></div>

<div id="manual" class="warn hidden">
<b>Trendyol رفض اتصال Render بـ HTTP 403.</b>
<p>أدخل روابط المنتجات المباشرة، رابط في كل سطر.</p>
<textarea id="manualUrls" rows="7" placeholder="https://www.trendyol.com/...-p-123456"></textarea>
<button onclick="manualAnalyze()">تحليل الروابط</button>
</div>
</div>

<div id="results" class="hidden">
<div class="grid">
<div class="stat">المنتجات<h2 id="total">0</h2></div>
<div class="stat">متوسط السعر<h2 id="avg">0 TL</h2></div>
<div class="stat">أقل سعر<h2 id="min">0 TL</h2></div>
<div class="stat">أعلى سعر<h2 id="max">0 TL</h2></div>
<div class="stat">Opportunity<h2 id="score">0/100</h2></div>
</div>

<div class="card">
<h2>التقرير</h2>
<pre id="report"></pre>
</div>

<div class="card">
<h2>المنتجات — روابط مباشرة</h2>
<div id="products" class="grid"></div>
</div>
</div>
</div>

<script>
function esc(s){
  return String(s ?? "").replaceAll("&","&amp;").replaceAll("<","&lt;")
    .replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#039;");
}

async function analyze(){
  hideError();
  const url=document.getElementById("url").value.trim();
  if(!url){showError("ضع رابط Trendyol أولاً.");return;}

  const res=await fetch("/api/analyze",{
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify({
      url,
      storeName:document.getElementById("storeName").value,
      category:document.getElementById("category").value,
      budget:document.getElementById("budget").value
    })
  });
  const data=await res.json();

  if(data.type==="TRENDYOL_403"){
    document.getElementById("manual").classList.remove("hidden");
    showError("Trendyol رفض طلب Render بـ HTTP 403. استعمل الوضع اليدوي أدناه.");
    return;
  }
  if(!res.ok){showError(data.error || "فشل التحليل.");return;}
  showResults(data);
}

async function manualAnalyze(){
  hideError();
  const urls=document.getElementById("manualUrls").value.split("\\n").map(x=>x.trim()).filter(Boolean);
  const res=await fetch("/api/manual",{
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify({
      urls,
      storeName:document.getElementById("storeName").value,
      category:document.getElementById("category").value,
      budget:document.getElementById("budget").value
    })
  });
  const data=await res.json();
  if(!res.ok){showError(data.error || "فشل التحليل.");return;}
  showResults(data);
}

function showResults(data){
  const s=data.statistics;
  document.getElementById("total").textContent=s.products_collected;
  document.getElementById("avg").textContent=s.average_price+" TL";
  document.getElementById("min").textContent=s.min_price+" TL";
  document.getElementById("max").textContent=s.max_price+" TL";
  document.getElementById("score").textContent=s.opportunity_score+"/100";
  document.getElementById("report").textContent=data.report;

  const box=document.getElementById("products");
  box.innerHTML="";
  data.products.forEach(p=>{
    const d=document.createElement("div");
    d.className="product";
    d.innerHTML=
      (p.image ? `<img src="${esc(p.image)}">` : "")+
      `<h3>${esc(p.title)}</h3>
       <p>السعر: <b>${p.price || "غير متاح"} TL</b></p>
       <p>التقييم: <b>${p.rating ?? "غير متاح"}</b></p>
       <p>المراجعات: <b>${p.review_count ?? "غير متاح"}</b></p>
       <p>Opportunity: <b>${p.opportunity_score}/100</b></p>
       <a href="${esc(p.url)}" target="_blank" rel="noopener noreferrer">🔗 فتح المنتج مباشرة</a>`;
    box.appendChild(d);
  });
  document.getElementById("results").classList.remove("hidden");
}

function showError(x){
  const e=document.getElementById("error");
  e.textContent=x;e.classList.remove("hidden");
}
function hideError(){document.getElementById("error").classList.add("hidden");}
</script>
</body>
</html>
"""

def fetch_trendyol(url):
    try:
        r = requests.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT,
            allow_redirects=True
        )
    except requests.RequestException as e:
        raise RuntimeError("تعذر الاتصال بـ Trendyol: " + str(e))

    if r.status_code == 403:
        raise PermissionError("Trendyol returned HTTP 403")
    if r.status_code == 429:
        raise RuntimeError("Trendyol returned HTTP 429")
    if r.status_code >= 400:
        raise RuntimeError(f"Trendyol HTTP {r.status_code}")

    return r.text

def direct_product_url(url):
    if not url:
        return None
    absolute = urljoin("https://www.trendyol.com", url)
    parsed = urlparse(absolute)
    if "trendyol.com" not in parsed.netloc.lower():
        return None
    if not re.search(r"-p-\d+", parsed.path.lower()):
        return None
    return "https://www.trendyol.com" + parsed.path

def get_product_id(url):
    m = re.search(r"-p-(\d+)", url or "", re.I)
    return m.group(1) if m else None

def parse_price(text):
    if not text:
        return 0
    patterns = re.findall(r"\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?", text)
    for x in patterns:
        try:
            n = float(x.replace(".", "").replace(",", "."))
            if 1 <= n <= 1000000:
                return round(n, 2)
        except ValueError:
            pass
    return 0

def parse_rating(text):
    if not text:
        return None
    for x in re.findall(r"\d(?:[.,]\d+)?", text):
        try:
            n = float(x.replace(",", "."))
            if 0 <= n <= 5:
                return n
        except ValueError:
            pass
    return None

def parse_reviews(text):
    if not text:
        return None
    nums = []
    for x in re.findall(r"\d[\d.]*", text):
        try:
            n = int(x.replace(".", ""))
            if n > 0:
                nums.append(n)
        except ValueError:
            pass
    return max(nums) if nums else None

def extract_products(html):
    soup = BeautifulSoup(html, "html.parser")
    products = []
    seen = set()

    for a in soup.find_all("a", href=True):
        url = direct_product_url(a.get("href"))
        if not url:
            continue

        pid = get_product_id(url)
        if not pid or pid in seen:
            continue
        seen.add(pid)

        title = (
            a.get("title")
            or a.get("aria-label")
            or a.get_text(" ", strip=True)
            or f"Trendyol Product {pid}"
        )

        img = a.find("img")
        image = ""
        if img:
            image = img.get("src") or img.get("data-src") or ""
            if image.startswith("//"):
                image = "https:" + image

        parent = a.parent
        text = parent.get_text(" ", strip=True) if parent else ""

        products.append({
            "id": pid,
            "title": title[:250],
            "price": parse_price(text),
            "rating": parse_rating(text),
            "review_count": parse_reviews(text),
            "image": image,
            "url": url,
            "is_direct_product": True
        })

        if len(products) >= MAX_PRODUCTS:
            break

    return products

def score_products(products):
    prices = [p["price"] for p in products if p["price"] > 0]
    avg = statistics.mean(prices) if prices else 0
    spread = statistics.pstdev(prices) if len(prices) > 1 else 0

    price_score = 50
    if avg:
        price_score = max(0, min(100, round(70 - (spread / avg) * 60)))

    seo_values = []
    for p in products:
        s = 50
        if 30 <= len(p["title"]) <= 120:
            s += 25
        if len(p["title"].split()) >= 5:
            s += 15
        seo_values.append(min(100, s))
    seo_score = round(statistics.mean(seo_values)) if seo_values else 50

    ratings = [p["rating"] for p in products if p["rating"] is not None]
    rating_score = round(statistics.mean(ratings) / 5 * 100) if ratings else 50

    reviews = [p["review_count"] for p in products if p["review_count"]]
    review_score = 50
    if reviews:
        review_score = min(100, round(30 + (statistics.mean(reviews) ** 0.5) * 8))

    opportunity = round(
        price_score * 0.25 +
        seo_score * 0.25 +
        rating_score * 0.20 +
        review_score * 0.30
    )

    for p in products:
        s = 50
        if p["price"] > 0:
            s += 10
        if len(p["title"]) >= 40:
            s += 10
        if p["rating"] is not None:
            if p["rating"] >= 4.5:
                s += 15
            elif p["rating"] >= 4:
                s += 8
        if p["review_count"]:
            if p["review_count"] >= 1000:
                s += 15
            elif p["review_count"] >= 100:
                s += 10
            elif p["review_count"] >= 20:
                s += 5
        p["opportunity_score"] = min(100, s)

    return {
        "products_collected": len(products),
        "min_price": round(min(prices), 2) if prices else 0,
        "max_price": round(max(prices), 2) if prices else 0,
        "average_price": round(avg, 2) if avg else 0,
        "price_score": price_score,
        "seo_score": seo_score,
        "rating_score": rating_score,
        "review_score": review_score,
        "opportunity_score": opportunity
    }

def make_report(store, category, budget, products, stats):
    top = sorted(
        products,
        key=lambda x: x.get("opportunity_score", 0),
        reverse=True
    )[:5]

    top_text = ""
    for i, p in enumerate(top, 1):
        top_text += (
            f"{i}. {p['title']}\n"
            f"السعر: {p['price']} TL\n"
            f"Opportunity: {p['opportunity_score']}/100\n"
            f"الرابط المباشر: {p['url']}\n\n"
        )

    return f"""
📊 التقرير الاستخباراتي الشامل — Active Online

المتجر: {store}
الفئة: {category}
عدد المنتجات المحللة: {stats['products_collected']}

1. تحليل الأسعار
متوسط السعر: {stats['average_price']} TL
أقل سعر: {stats['min_price']} TL
أعلى سعر: {stats['max_price']} TL
Price Score: {stats['price_score']}/100

2. Trendyol SEO
SEO Score: {stats['seo_score']}/100
التوصيات:
• وضع الكلمة المفتاحية الأساسية في بداية العنوان.
• كتابة عناوين واضحة باللغة التركية.
• إضافة كلمات تصف النوع والخامة والاستخدام.
• تجنب حشو الكلمات.

3. التقييمات والمراجعات
Rating Score: {stats['rating_score']}/100
Review Score: {stats['review_score']}/100

4. Opportunity
Opportunity Score: {stats['opportunity_score']}/100

5. أفضل المنتجات
{top_text}

6. الإعلانات
الميزانية المقترحة: {budget:,.2f} TL
اقتراح مبدئي:
Meta Ads: 40%
Google Ads: 25%
Trendyol Ads: 25%
Retargeting: 10%

7. خطة 30 يوم
الأسبوع 1: تحسين العناوين والصور والمنتجات.
الأسبوع 2: اختبار الإعلانات.
الأسبوع 3: إيقاف المنتجات الضعيفة وتوسيع المنتجات الأفضل.
الأسبوع 4: مراجعة ROAS وتجهيز خطة الشهر التالي.

⚠️ الأرقام التقديرية ليست ضماناً للمبيعات.
"""

def products_from_urls(urls):
    products = []
    seen = set()

    for raw in urls:
        url = direct_product_url(raw)
        if not url:
            continue
        pid = get_product_id(url)
        if not pid or pid in seen:
            continue
        seen.add(pid)
        products.append({
            "id": pid,
            "title": f"Trendyol Product {pid}",
            "price": 0,
            "rating": None,
            "review_count": None,
            "image": "",
            "url": url,
            "is_direct_product": True,
            "opportunity_score": 50
        })

    return products

@app.route("/")
def home():
    return render_template_string(HTML)

@app.route("/api/analyze", methods=["POST"])
def analyze():
    data = request.get_json(silent=True) or {}
    url = str(data.get("url", "")).strip()
    store = str(data.get("storeName", "Trendyol Store"))
    category = str(data.get("category", "عام"))

    try:
        budget = float(data.get("budget", 10000))
    except (TypeError, ValueError):
        budget = 10000

    if not url:
        return jsonify({"error": "أدخل رابط Trendyol"}), 400

    try:
        html = fetch_trendyol(url)
    except PermissionError:
        return jsonify({
            "type": "TRENDYOL_403",
            "error": "Trendyol رفض اتصال Render بـ HTTP 403."
        }), 403
    except Exception as e:
        return jsonify({"error": str(e)}), 502

    products = extract_products(html)
    if not products:
        return jsonify({
            "error": "لم نجد روابط منتجات مباشرة داخل الصفحة."
        }), 422

    stats = score_products(products)
    report = make_report(store, category, budget, products, stats)

    return jsonify({
        "status": "success",
        "store_info": {"store_name": store, "url": url},
        "statistics": stats,
        "products": products,
        "report": report
    })

@app.route("/api/manual", methods=["POST"])
def manual():
    data = request.get_json(silent=True) or {}
    store = str(data.get("storeName", "Trendyol Store"))
    category = str(data.get("category", "عام"))

    try:
        budget = float(data.get("budget", 10000))
    except (TypeError, ValueError):
        budget = 10000

    products = products_from_urls(data.get("urls", []))
    if not products:
        return jsonify({
            "error": "لا توجد روابط منتجات صحيحة. يجب أن يحتوي الرابط على -p-رقم."
        }), 422

    stats = score_products(products)
    report = make_report(store, category, budget, products, stats)

    return jsonify({
        "status": "success",
        "store_info": {"store_name": store},
        "statistics": stats,
        "products": products,
        "report": report
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
