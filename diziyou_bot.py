import requests
from bs4 import BeautifulSoup
import json
import re
import time
import os
import sys

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
        
        # Klasörleri oluştur
        os.makedirs(JSON_DIR, exist_ok=True)

    def get_total_pages(self):
        """Arşivdeki toplam sayfa sayısını bulur."""
        try:
            print("📄 Toplam sayfa sayısı hesaplanıyor...")
            response = self.session.get(FIRST_PAGE_URL, timeout=15)
            soup = BeautifulSoup(response.content, "html.parser")
            
            # Sayfalama alanını bul
            pagination = soup.select(".paginate-links .page-numbers")
            if pagination:
                # "Next" butonu hariç en son sayıyı al
                numbers = [int(p.get_text(strip=True)) for p in pagination if p.get_text(strip=True).isdigit()]
                max_page = max(numbers) if numbers else 1
                print(f"✅ Toplam Sayfa: {max_page}")
                return max_page
            return 1
        except Exception as e:
            print(f"❌ Sayfa sayısı alınamadı, varsayılan 1 kullanılıyor. Hata: {e}")
            return 1

    def get_series_links_from_page(self, page_num):
        """Bir arşiv sayfasındaki tüm dizi linklerini çeker."""
        url = ARCHIVE_URL_TEMPLATE.format(page_num)
        if page_num == 1:
            url = FIRST_PAGE_URL
            
        print(f"📂 Arşiv Sayfası Taranıyor: {page_num} ({url})")
        try:
            response = self.session.get(url, timeout=15)
            soup = BeautifulSoup(response.content, "html.parser")
            
            # .single-item içindeki linkleri al
            series_elements = soup.select(".single-item .cat-img a")
            links = [a['href'] for a in series_elements if 'href' in a.attrs]
            return links
        except Exception as e:
            print(f"⚠️ Sayfa {page_num} taranamadı: {e}")
            return []

    def get_video_id(self, episode_url):
        """Bölüm sayfasındaki iframe ID'sini çeker."""
        try:
            response = self.session.get(episode_url, timeout=10)
            if response.status_code != 200: return None
            
            soup = BeautifulSoup(response.content, "html.parser")
            iframe = soup.select_one("iframe#diziyouPlayer")
            
            if iframe and 'src' in iframe.attrs:
                # Regex ile ID'yi al (player/40901.html -> 40901)
                match = re.search(r"player\/(\d+)\.html", iframe['src'])
                if match:
                    return match.group(1)
            return None
        except:
            return None

    def process_series(self, series_url):
        """Bir dizinin tüm bölümlerini tarar ve JSON/M3U verisi oluşturur."""
        try:
            response = self.session.get(series_url, timeout=15)
            soup = BeautifulSoup(response.content, "html.parser")

            # Dizi Başlığı
            title_tag = soup.select_one("h1.title-border")
            series_title = title_tag.get_text(strip=True).replace("izle", "").strip() if title_tag else "Bilinmeyen Dizi"
            
            # Poster
            poster_tag = soup.select_one(".cat-img img")
            poster_url = poster_tag['src'] if poster_tag else ""
            
            # Dosya adı için güvenli başlık (Breaking Bad -> breaking_bad)
            safe_filename = re.sub(r'[^a-zA-Z0-9]', '_', series_title.lower())
            
            series_data = {
                "title": series_title,
                "url": series_url,
                "poster": poster_url,
                "episodes": []
            }

            # Bölümleri Bul
            episodes = soup.select("#scrollbar-container .container a")
            print(f"  🎬 Dizi: {series_title} | {len(episodes)} Bölüm Bulundu.")

            for ep in episodes:
                ep_link = ep['href']
                baslik_div = ep.select_one(".baslik")
                ep_full_text = baslik_div.get_text(strip=True)
                
                # Sezon/Bölüm adını temizle
                ep_name = ep_full_text.split("(")[0].strip()
                
                # Video ID al
                vid_id = self.get_video_id(ep_link)
                
                if vid_id:
                    # Linkleri oluştur
                    sub_link = f"https://storage.diziyou.one/episodes/{vid_id}/play.m3u8"
                    dub_link = f"https://storage.diziyou.one/episodes/{vid_id}_tr/play.m3u8"
                    
                    # JSON Ekle
                    series_data["episodes"].append({
                        "name": ep_name,
                        "id": vid_id,
                        "sub_stream": sub_link,
                        "dub_stream": dub_link
                    })

                    # M3U Ekle (Altyazılı)
                    self.m3u_entries.append(
                        f'#EXTINF:-1 tvg-logo="{poster_url}" group-title="{series_title}", {series_title} - {ep_name} (TR Altyazı)\n{sub_link}'
                    )
                    # M3U Ekle (Dublaj)
                    self.m3u_entries.append(
                        f'#EXTINF:-1 tvg-logo="{poster_url}" group-title="{series_title}", {series_title} - {ep_name} (TR Dublaj)\n{dub_link}'
                    )
                
                time.sleep(0.1) # Sunucuyu yormamak için çok kısa bekleme

            # Diziyi JSON olarak kaydet
            json_path = os.path.join(JSON_DIR, f"{safe_filename}.json")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(series_data, f, ensure_ascii=False, indent=4)
            
            return True

        except Exception as e:
            print(f"  ❌ Hata ({series_url}): {e}")
            return False

    def run(self):
        total_pages = self.get_total_pages()
        
        # Test için sayfa sayısını limitleyebilirsin (Örn: range(1, 2) sadece ilk sayfayı tarar)
        # Hepsini taramak için: range(1, total_pages + 1)
        # GitHub Actions süresi yetmezse bu sayıyı düşür veya mantığı değiştir.
        for page in range(1, 3): # Şimdilik sadece ilk 2 sayfayı tarayacak şekilde ayarladım. Hepsini istersen `total_pages + 1` yap.
            series_links = self.get_series_links_from_page(page)
            
            for link in series_links:
                self.process_series(link)
                time.sleep(1) # Dizi geçişlerinde bekleme

        # En sonda M3U dosyasını kaydet
        m3u_path = os.path.join(OUTPUT_DIR, "diziyou_full.m3u")
        with open(m3u_path, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            f.write("\n".join(self.m3u_entries))
        
        print(f"\n✅ Tarama Tamamlandı! Dosyalar '{OUTPUT_DIR}' klasörüne kaydedildi.")

if __name__ == "__main__":
    scraper = DiziyouFullScraper()
    scraper.run()
