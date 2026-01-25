import requests
from bs4 import BeautifulSoup
import json
import re
import time
import os

# --- AYARLAR ---
BASE_URL = "https://www.diziyou.one"
ARCHIVE_URL_TEMPLATE = "https://www.diziyou.one/dizi-arsivi/page/{}/?filtrele=alfabetik&sirala=ASC"
FIRST_PAGE_URL = "https://www.diziyou.one/dizi-arsivi/?filtrele=alfabetik&sirala=ASC"

# Çıktı Klasörleri
OUTPUT_DIR = "data"
JSON_DIR = os.path.join(OUTPUT_DIR, "series")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.diziyou.one/"
}

class DiziyouFullScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.m3u_entries = []
        os.makedirs(JSON_DIR, exist_ok=True)

    def get_total_pages(self):
        """Arşivdeki gerçek sayfa sayısını bulur."""
        try:
            response = self.session.get(FIRST_PAGE_URL, timeout=15)
            soup = BeautifulSoup(response.content, "html.parser")
            pagination = soup.select(".paginate-links .page-numbers")
            if pagination:
                numbers = [int(p.get_text(strip=True)) for p in pagination if p.get_text(strip=True).isdigit()]
                return max(numbers) if numbers else 1
            return 1
        except:
            return 87 # Hata olursa bilinen son sayfa

    def get_video_id(self, episode_url):
        """Bölüm sayfasından Player ID çeker."""
        try:
            response = self.session.get(episode_url, timeout=10)
            soup = BeautifulSoup(response.content, "html.parser")
            iframe = soup.select_one("iframe#diziyouPlayer")
            if iframe and 'src' in iframe.attrs:
                match = re.search(r"player\/(\d+)\.html", iframe['src'])
                if match: return match.group(1)
            return None
        except:
            return None

    def process_series(self, series_url):
        """Dizi bilgilerini ve tüm bölümlerini işler."""
        try:
            response = self.session.get(series_url, timeout=15)
            soup = BeautifulSoup(response.content, "html.parser")

            # Daha sağlam başlık çekme
            title_tag = soup.select_one("h1.title-border")
            if not title_tag: return False
            
            series_title = title_tag.get_text(strip=True).replace("izle", "").strip()
            # Eğer başlık hala boşsa URL'den tahmin et
            if not series_title:
                series_title = series_url.split('/')[-2].replace('-', ' ').title()

            poster_tag = soup.select_one(".cat-img img") or soup.select_one(".category_image img")
            poster_url = poster_tag['src'] if poster_tag else ""
            
            safe_filename = re.sub(r'[^a-zA-Z0-9]', '_', series_title.lower())
            
            series_data = {
                "title": series_title,
                "url": series_url,
                "poster": poster_url,
                "episodes": []
            }

            episodes = soup.select("#scrollbar-container .container a")
            if not episodes:
                print(f"  ⚠️ {series_title}: Bölüm bulunamadı, atlanıyor.")
                return False

            print(f"  🎬 Dizi: {series_title} | {len(episodes)} Bölüm İşleniyor...")

            for ep in episodes:
                ep_link = ep['href']
                baslik_div = ep.select_one(".baslik")
                ep_name = baslik_div.get_text(strip=True).split("(")[0].strip() if baslik_div else "Bölüm"
                
                vid_id = self.get_video_id(ep_link)
                if vid_id:
                    sub_link = f"https://storage.diziyou.one/episodes/{vid_id}/play.m3u8"
                    dub_link = f"https://storage.diziyou.one/episodes/{vid_id}_tr/play.m3u8"
                    
                    series_data["episodes"].append({
                        "name": ep_name,
                        "id": vid_id,
                        "sub": sub_link,
                        "dub": dub_link
                    })

                    self.m3u_entries.append(f'#EXTINF:-1 tvg-logo="{poster_url}" group-title="{series_title}", {series_title} - {ep_name} (Altyazı)\n{sub_link}')
                    self.m3u_entries.append(f'#EXTINF:-1 tvg-logo="{poster_url}" group-title="{series_title}", {series_title} - {ep_name} (Dublaj)\n{dub_link}')
                
                time.sleep(0.05) # Hızlandırmak için süreyi düşürdüm

            # JSON Kaydet
            with open(os.path.join(JSON_DIR, f"{safe_filename}.json"), "w", encoding="utf-8") as f:
                json.dump(series_data, f, ensure_ascii=False, indent=4)
            return True

        except Exception as e:
            print(f"  ❌ Hata {series_url}: {e}")
            return False

    def run(self):
        max_pages = self.get_total_pages()
        limit = min(max_pages, 100) # 100 sayfa sınırı
        
        print(f"🚀 Toplam {limit} sayfa taranacak...")

        for page in range(1, limit + 1):
            url = ARCHIVE_URL_TEMPLATE.format(page) if page > 1 else FIRST_PAGE_URL
            print(f"\n📂 Sayfa {page}/{limit} Taranıyor...")
            
            try:
                response = self.session.get(url, timeout=15)
                soup = BeautifulSoup(response.content, "html.parser")
                series_links = [a['href'] for a in soup.select(".single-item .cat-img a")]
                
                for link in series_links:
                    self.process_series(link)
                    time.sleep(0.5) # Sunucu koruması
                    
            except Exception as e:
                print(f"  ⚠️ Sayfa {page} hatası: {e}")

        # Final M3U
        with open(os.path.join(OUTPUT_DIR, "diziyou_full.m3u"), "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n" + "\n".join(self.m3u_entries))
        
        print(f"\n✅ BİTTİ! 'data' klasörünü kontrol et.")

if __name__ == "__main__":
    scraper = DiziyouFullScraper()
    scraper.run()
