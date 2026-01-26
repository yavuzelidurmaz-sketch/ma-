import time
import json
import re
import os
import random
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# --- AYARLAR ---
BASE_URL = "https://www.filmmodu.ws"
ARCHIVE_URL_TEMPLATE = "https://www.filmmodu.ws/arsiv-filmler?page={}"
FIRST_PAGE_URL = "https://www.filmmodu.ws/arsiv-filmler"

# Çıktı Klasörleri
OUTPUT_DIR = "data"
JSON_DIR = os.path.join(OUTPUT_DIR, "movies")
M3U_FILE = os.path.join(OUTPUT_DIR, "filmmodu_playlist.m3u")

class FilmModuScraper:
    def __init__(self):
        # Klasörleri oluştur
        os.makedirs(JSON_DIR, exist_ok=True)
        
        # M3U dosyasını başlat (Eğer yoksa başlık ekle)
        if not os.path.exists(M3U_FILE):
            with open(M3U_FILE, "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")

    def setup_driver(self):
        """Headless (görünmez) Chrome tarayıcıyı başlatır."""
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver

    def extract_hidden_links(self, html_content):
        """
        Sayfa kaynağındaki gizli .m3u8 ve .vtt linklerini Regex ile bulur.
        imgsapi.pro, uploads/subs vb. hepsini yakalar.
        """
        links = {
            "m3u8": [],
            "vtt": []
        }
        
        # M3U8 Linkleri için Regex (imgsapi.pro vb. dahil)
        # http ile başlayıp .m3u8 ile biten stringleri bulur
        video_regex = r'(https?://[^\s"\'<>]+?\.m3u8)'
        video_matches = re.findall(video_regex, str(html_content))
        links["m3u8"] = list(set(video_matches)) # Tekrarları temizle

        # VTT (Altyazı) Linkleri için Regex
        # http ile başlayıp .vtt ile biten stringleri bulur
        subtitle_regex = r'(https?://[^\s"\'<>]+?\.vtt)'
        subtitle_matches = re.findall(subtitle_regex, str(html_content))
        links["vtt"] = list(set(subtitle_matches))
        
        return links

    def append_to_m3u(self, entries):
        """M3U dosyasına anlık ekleme yapar."""
        if not entries: return
        with open(M3U_FILE, "a", encoding="utf-8") as f:
            f.write("\n".join(entries) + "\n")

    def run(self):
        driver = self.setup_driver()
        
        # Kaç sayfa taranacak? (Test için 5 yaptım, hepsini istersen 500 yap)
        TOTAL_PAGES_TO_SCRAPE = 5 
        
        print(f"🚀 FilmModu Tarayıcı Başlatılıyor... ({TOTAL_PAGES_TO_SCRAPE} sayfa)")

        try:
            for page in range(1, TOTAL_PAGES_TO_SCRAPE + 1):
                url = ARCHIVE_URL_TEMPLATE.format(page) if page > 1 else FIRST_PAGE_URL
                print(f"\n📂 Sayfa {page} taranıyor: {url}")
                
                driver.get(url)
                time.sleep(2) # Sayfa yüklenmesi için bekle
                
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                movie_cards = soup.select('.row.movie-list .movie')

                if not movie_cards:
                    print("⚠️ Bu sayfada film bulunamadı.")
                    continue

                for card in movie_cards:
                    try:
                        # 1. Temel Bilgileri Al (filmmoduana.txt yapısına göre)
                        title_tag = card.select_one('.detail .original-name')
                        tr_title_tag = card.select_one('.detail .turkish-name')
                        link_tag = card.find('a')
                        img_tag = card.select_one('img')

                        if not link_tag: continue

                        title = title_tag.text.strip() if title_tag else "Bilinmeyen Film"
                        if tr_title_tag and tr_title_tag.text.strip():
                            title = f"{title} ({tr_title_tag.text.strip()})"
                        
                        movie_url = link_tag['href']
                        if not movie_url.startswith('http'):
                            movie_url = BASE_URL + movie_url
                        
                        poster = ""
                        if img_tag:
                            poster = img_tag.get('data-src') or img_tag.get('src') or ""

                        safe_filename = re.sub(r'[^a-zA-Z0-9]', '_', title.lower())
                        json_path = os.path.join(JSON_DIR, f"{safe_filename}.json")

                        # Eğer film zaten indirilmişse atla (Zaman kazanmak için)
                        if os.path.exists(json_path):
                            # print(f"  ⏭️ {title} zaten var.")
                            continue

                        print(f"  🎬 İşleniyor: {title}")

                        # 2. Film Detay Sayfasına Git
                        driver.get(movie_url)
                        time.sleep(random.uniform(3.0, 5.0)) # Player ve JS'in yüklenmesi için bekle
                        
                        # 3. Gizli Linkleri Çıkar
                        page_source = driver.page_source
                        hidden_links = self.extract_hidden_links(page_source)

                        # Veriyi Hazırla
                        movie_data = {
                            "title": title,
                            "url": movie_url,
                            "poster": poster,
                            "sources": []
                        }

                        m3u_entries = []

                        # M3U8 Linklerini Ekle
                        for i, m3u8_link in enumerate(hidden_links["m3u8"]):
                            label = f"Kaynak {i+1}"
                            if "imgsapi" in m3u8_link: label = "ImgsApi (Hızlı)"
                            
                            movie_data["sources"].append({"type": "video", "url": m3u8_link})
                            
                            # M3U Formatı
                            m3u_entries.append(f'#EXTINF:-1 tvg-logo="{poster}" group-title="FilmModu Movies", {title} [{label}]')
                            m3u_entries.append(m3u8_link)

                        # VTT Altyazı Linklerini Ekle (JSON'a ekler, M3U desteklemez ama ek bilgi olarak koyarız)
                        for vtt_link in hidden_links["vtt"]:
                             movie_data["sources"].append({"type": "subtitle", "url": vtt_link})
                             # M3U'ya yorum olarak ekle (Player'lar bazen okur)
                             m3u_entries.append(f'#EXT-X-SUBTITLE: {vtt_link}')

                        # Eğer hiç link bulamazsa, en azından sayfa linkini ekle
                        if not hidden_links["m3u8"]:
                            print(f"    ⚠️ Link bulunamadı, sayfa linki eklendi.")
                            movie_data["sources"].append({"type": "page", "url": movie_url})
                            m3u_entries.append(f'#EXTINF:-1 tvg-logo="{poster}" group-title="FilmModu Web", {title} [Web]')
                            m3u_entries.append(movie_url)

                        # 4. Kaydet (JSON ve M3U)
                        with open(json_path, "w", encoding="utf-8") as f:
                            json.dump(movie_data, f, ensure_ascii=False, indent=4)
                        
                        self.append_to_m3u(m3u_entries)

                    except Exception as e:
                        print(f"  ❌ Film hatası ({title}): {e}")
                        continue
        
        except Exception as e:
            print(f"❌ Genel Hata: {e}")
        finally:
            driver.quit()
            print("✅ Tarama tamamlandı.")

if __name__ == "__main__":
    scraper = FilmModuScraper()
    scraper.run()
