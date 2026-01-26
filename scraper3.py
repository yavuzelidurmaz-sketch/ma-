import time
import json
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# Ayarlar
BASE_URL = "https://www.filmmodu.ws"
ARCHIVE_URL = "https://www.filmmodu.ws/arsiv-filmler"

def setup_driver():
    """Headless (görünmez) Chrome tarayıcıyı başlatır."""
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Arayüzsüz mod
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def find_media_links(html_content):
    """
    Sayfa kaynağındaki .m3u8 ve .vtt linklerini Regex ile bulur.
    Her türlü domaini (imgsapi.pro, filmmodu.ws vb.) kapsar.
    """
    media_files = {
        "video": [],
        "subtitle": []
    }
    
    # M3U8 Linkleri için Regex (imgsapi.pro vb. dahil)
    # Tırnak işaretleri, boşluk veya < > karakterleri arasında kalan ve .m3u8 ile biten linkleri alır
    video_regex = r'(https?://[^\s"\'<>]+?\.m3u8)'
    video_matches = re.findall(video_regex, str(html_content))
    # Benzersizleri al
    media_files["video"] = list(set(video_matches))

    # VTT (Altyazı) Linkleri için Regex
    subtitle_regex = r'(https?://[^\s"\'<>]+?\.vtt)'
    subtitle_matches = re.findall(subtitle_regex, str(html_content))
    media_files["subtitle"] = list(set(subtitle_matches))
    
    return media_files

def scrape_movies():
    driver = setup_driver()
    movies_data = []

    try:
        print("Arşiv sayfası taranıyor...")
        driver.get(ARCHIVE_URL)
        time.sleep(3) # Sayfanın yüklenmesini bekle
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        movie_cards = soup.select('.row.movie-list .movie')
        
        print(f"Toplam {len(movie_cards)} film bulundu.")

        # Test için ilk 5 filmi çekelim (Sunucuyu yormamak için)
        # Hepsini çekmek için [:5] kısmını kaldırın.
        for card in movie_cards[:5]: 
            try:
                # Başlık ve Link Alma
                title_tag = card.select_one('.detail .original-name')
                tr_title_tag = card.select_one('.detail .turkish-name')
                link_tag = card.find('a')
                img_tag = card.select_one('img')

                if not link_tag: continue

                title = title_tag.text.strip() if title_tag else "Bilinmeyen"
                if tr_title_tag and tr_title_tag.text.strip():
                    title = f"{title} ({tr_title_tag.text.strip()})"
                
                movie_url = link_tag['href']
                if not movie_url.startswith('http'):
                    movie_url = BASE_URL + movie_url
                
                poster = img_tag.get('data-src') or img_tag.get('src') or ""

                print(f"Film işleniyor: {title}")

                # Film Sayfasına Git
                driver.get(movie_url)
                time.sleep(4) # JavaScript'in player'ı yüklemesi için bekleme süresi
                
                # Sayfa kaynağını al ve linkleri ara
                page_source = driver.page_source
                media = find_media_links(page_source)

                sources = []
                
                # Bulunan Videoları Ekle
                for vid in media["video"]:
                    sources.append({
                        "type": "video",
                        "label": "Stream (M3U8)",
                        "url": vid
                    })
                
                # Bulunan Altyazıları Ekle
                for sub in media["subtitle"]:
                    sources.append({
                        "type": "subtitle",
                        "label": "Altyazı (VTT)",
                        "url": sub
                    })

                # Eğer hiç video bulamazsa sayfa linkini koy (Fallback)
                if not sources:
                    sources.append({
                        "type": "page",
                        "label": "Sayfa Linki",
                        "url": movie_url
                    })

                movies_data.append({
                    "title": title,
                    "poster": poster,
                    "page_url": movie_url,
                    "sources": sources
                })

            except Exception as e:
                print(f"Hata ({title}): {e}")
                continue

    finally:
        driver.quit()

    return movies_data

def save_to_json(data, filename="filmler.json"):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print
