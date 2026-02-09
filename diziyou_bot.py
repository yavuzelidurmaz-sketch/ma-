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
            return 87

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

    def extract_meta_info(self, soup):
        """Sayfadan detaylı meta bilgileri (IMDb, Oyuncular, Tür vb.) çeker."""
        meta = {
            "imdb_score": "0.0",
            "imdb_id": None,
            "genres": [],
            "cast": [],
            "year": "",
            "summary": "",
            "country": ""
        }

        try:
            # 1. IMDb Puanı
            imdb_box = soup.select_one(".imdb-puan span") or soup.select_one(".imdb-score")
            if imdb_box:
                meta["imdb_score"] = imdb_box.get_text(strip=True)

            # 2. IMDb ID (Linklerden bulmaya çalışır)
            imdb_link = soup.find('a', href=re.compile(r'imdb\.com/title/tt'))
            if imdb_link:
                match = re.search(r'(tt\d+)', imdb_link['href'])
                if match:
                    meta["imdb_id"] = match.group(1)

            # 3. Türler (Categories)
            genres = soup.select(".dizibilgi a[href*='/tur/']")
            meta["genres"] = [g.get_text(strip=True) for g in genres]

            # 4. Oyuncular
            # Genelde 'Oyuncular' başlığı altındaki liste veya linkler
            cast_list = soup.select(".oyuncular a") or soup.select(".cast-list a")
            meta["cast"] = [c.get_text(strip=True) for c in cast_list if c.get_text(strip=True)]

            # 5. Yapım Yılı
            year_tag = soup.find("span", string=re.compile(r"Yapım Yılı"))
            if year_tag and year_tag.parent:
                meta["year"] = year_tag.parent.get_text(strip=True).replace("Yapım Yılı:", "").strip()
            else:
                 # Alternatif yıl bulma
                 yil_link = soup.select_one("a[href*='/yil/']")
                 if yil_link: meta["year"] = yil_link.get_text(strip=True)

            # 6. Ülke
            country_tag = soup.find("span", string=re.compile(r"Ülke"))
            if country_tag and country_tag.parent:
                 meta["country"] = country_tag.parent.get_text(strip=True).replace("Ülke:", "").strip()

            # 7. Özet (Summary)
            summary_div = soup.select_one(".dizi-ozeti") or soup.select_one(".entry-content p") or soup.select_one("#movie-synopsis")
            if summary_div:
                meta["summary"] = summary_div.get_text(strip=True)

        except Exception as e:
            print(f"  ⚠️ Meta veri çekilirken hata: {e}")
        
        return meta

    def process_series(self, series_url):
        """Dizi bilgilerini ve tüm bölümlerini işler."""
        try:
            response = self.session.get(series_url, timeout=15)
            soup = BeautifulSoup(response.content, "html.parser")

            # Başlık
            title_tag = soup.select_one("h1.title-border")
            if not title_tag: 
                # Alternatif başlık bulucu
                title_tag = soup.select_one("h1")
            
            if not title_tag: return False

            series_title = title_tag.get_text(strip=True).replace("izle", "").strip()
            if not series_title:
                series_title = series_url.split('/')[-2].replace('-', ' ').title()

            # Poster
            poster_tag = soup.select_one(".cat-img img") or soup.select_one(".category_image img") or soup.select_one(".poster img")
            poster_url = poster_tag['src'] if poster_tag else ""
            if poster_url and poster_url.startswith("/"): # Relative path düzeltme
                poster_url = BASE_URL + poster_url

            # --- YENİ EKLENEN KISIM: DETAYLI VERİLER ---
            meta_data = self.extract_meta_info(soup)
            
            safe_filename = re.sub(r'[^a-zA-Z0-9]', '_', series_title.lower())

            # Ana Veri Yapısı
            series_data = {
                "title": series_title,
                "original_title": series_title, # Genelde aynısıdır, varsa değiştirilebilir
                "url": series_url,
                "poster": poster_url,
                "imdb_score": meta_data["imdb_score"],
                "imdb_id": meta_data["imdb_id"],
                "release_year": meta_data["year"],
                "genres": meta_data["genres"],
                "cast": meta_data["cast"],
                "country": meta_data["country"],
                "summary": meta_data["summary"],
                "episodes": []
            }

            episodes = soup.select("#scrollbar-container .container a")
            if not episodes:
                print(f"  ⚠️ {series_title}: Bölüm bulunamadı, atlanıyor.")
                return False

            print(f"  🎬 {series_title} ({meta_data['year']}) | IMDb: {meta_data['imdb_score']} | {len(episodes)} Bölüm")

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

                    # M3U Genişletilmiş Metadata
                    # IPTV oynatıcıları için logo, grup ve başlık
                    m3u_info = f'#EXTINF:-1 tvg-id="{meta_data["imdb_id"]}" tvg-logo="{poster_url}" group-title="{series_title}" tvg-rating="{meta_data["imdb_score"]}", {series_title} - {ep_name}'
                    
                    self.m3u_entries.append(f'{m3u_info} (Altyazı)\n{sub_link}')
                    self.m3u_entries.append(f'{m3u_info} (Dublaj)\n{dub_link}')

                time.sleep(0.05)

            # JSON Kaydet
            with open(os.path.join(JSON_DIR, f"{safe_filename}.json"), "w", encoding="utf-8") as f:
                json.dump(series_data, f, ensure_ascii=False, indent=4)
            return True

        except Exception as e:
            print(f"  ❌ Hata {series_url}: {e}")
            return False

    def run(self):
        max_pages = self.get_total_pages()
        limit = min(max_pages, 100) # İstersen bu limiti kaldırabilirsin

        print(f"🚀 Gelişmiş Tarama Başladı: Toplam {limit} sayfa...")

        for page in range(1, limit + 1):
            url = ARCHIVE_URL_TEMPLATE.format(page) if page > 1 else FIRST_PAGE_URL
            print(f"\n📂 Sayfa {page}/{limit} Taranıyor...")

            try:
                response = self.session.get(url, timeout=15)
                soup = BeautifulSoup(response.content, "html.parser")
                # Dizi linklerini bul
                series_links = [a['href'] for a in soup.select(".single-item .cat-img a")]

                for link in series_links:
                    self.process_series(link)
                    time.sleep(0.5)

            except Exception as e:
                print(f"  ⚠️ Sayfa {page} hatası: {e}")

        # Final M3U
        with open(os.path.join(OUTPUT_DIR, "diziyou_full_extended.m3u"), "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n" + "\n".join(self.m3u_entries))

        print(f"\n✅ BİTTİ! Tüm veriler (JSON + M3U) 'data' klasörüne kaydedildi.")

if __name__ == "__main__":
    scraper = DiziyouFullScraper()
    scraper.run()
