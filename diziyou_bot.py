import requests
from bs4 import BeautifulSoup
import json
import re
import time
import os

# --- AYARLAR ---
BASE_URL = "https://www.diziyou.one"
# İstersen buraya birden fazla dizi linki ekleyebilirsin
TARGET_SERIES = [
    "https://www.diziyou.one/stranger-things/",
    # "https://www.diziyou.one/dizi-adi-2/"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.diziyou.one/"
}

class DiziyouScraper:
    def __init__(self):
        self.all_data = []
        self.m3u_content = "#EXTM3U\n"

    def get_video_id(self, episode_url):
        """Bölüm sayfasındaki iframe'den ID'yi (örn: 40901) çeker."""
        try:
            response = requests.get(episode_url, headers=HEADERS, timeout=10)
            if response.status_code != 200:
                return None
            
            soup = BeautifulSoup(response.content, "html.parser")
            
            # Iframe'i bul
            iframe = soup.select_one("iframe#diziyouPlayer")
            if iframe and 'src' in iframe.attrs:
                src = iframe['src']
                # Regex ile ID'yi al (player/40901.html -> 40901)
                match = re.search(r"player\/(\d+)\.html", src)
                if match:
                    return match.group(1)
            return None
        except Exception as e:
            print(f"Hata (ID Çekme): {e}")
            return None

    def scrape_series(self, series_url):
        print(f"Dizi Taranıyor: {series_url}")
        try:
            response = requests.get(series_url, headers=HEADERS)
            soup = BeautifulSoup(response.content, "html.parser")

            # Dizi Bilgileri
            title_tag = soup.select_one("h1.title-border")
            series_title = title_tag.get_text(strip=True).replace("izle", "").strip() if title_tag else "Bilinmeyen Dizi"
            
            poster_tag = soup.select_one(".cat-img img")
            poster_url = poster_tag['src'] if poster_tag else ""

            # Bölümleri Bul (#scrollbar-container içindeki linkler)
            episodes = soup.select("#scrollbar-container .container a")
            
            print(f"  > {len(episodes)} bölüm bulundu.")

            for ep in episodes:
                ep_link = ep['href']
                
                # Başlık ve Sezon/Bölüm ayrıştırma
                baslik_div = ep.select_one(".baslik")
                ep_full_title = baslik_div.get_text(strip=True)
                
                # "1. Sezon 1. Bölüm" formatını yakala
                ep_meta = "Bilinmeyen Bölüm"
                if "Sezon" in ep_full_title and "Bölüm" in ep_full_title:
                    ep_meta = ep_full_title.split("(")[0].strip() # Parantez öncesini al

                # Bölüm detayına git ve ID'yi al
                video_id = self.get_video_id(ep_link)
                
                if video_id:
                    # Linkleri Oluştur (Senin verdiğin mantık)
                    stream_sub = f"https://storage.diziyou.one/episodes/{video_id}/play.m3u8"
                    stream_dub = f"https://storage.diziyou.one/episodes/{video_id}_tr/play.m3u8"
                    sub_tr = f"https://storage.diziyou.one/subtitles/{video_id}/tr.vtt"
                    sub_en = f"https://storage.diziyou.one/subtitles/{video_id}/en.vtt"

                    # JSON için veri
                    ep_data = {
                        "series": series_title,
                        "episode_title": ep_meta,
                        "poster": poster_url,
                        "video_id": video_id,
                        "links": {
                            "subtitle_stream": stream_sub,
                            "dubbed_stream": stream_dub,
                            "subtitle_files": [sub_tr, sub_en]
                        }
                    }
                    self.all_data.append(ep_data)

                    # M3U Formatına Ekle (Türkçe Altyazılı)
                    self.m3u_content += f'#EXTINF:-1 tvg-logo="{poster_url}" group-title="{series_title}", {series_title} - {ep_meta} (Altyazılı)\n'
                    self.m3u_content += f"{stream_sub}\n"
                    
                    # M3U Formatına Ekle (Türkçe Dublaj)
                    self.m3u_content += f'#EXTINF:-1 tvg-logo="{poster_url}" group-title="{series_title}", {series_title} - {ep_meta} (Dublaj)\n'
                    self.m3u_content += f"{stream_dub}\n"

                    print(f"    + Eklendi: {ep_meta} (ID: {video_id})")
                else:
                    print(f"    - Video ID bulunamadı: {ep_meta}")
                
                # Sunucuyu yormamak için kısa bekleme
                time.sleep(0.5)

        except Exception as e:
            print(f"Dizi tarama hatası: {e}")

    def save_files(self):
        # JSON Kaydet
        with open("diziyou_playlist.json", "w", encoding="utf-8") as f:
            json.dump(self.all_data, f, ensure_ascii=False, indent=4)
        
        # M3U Kaydet
        with open("diziyou_playlist.m3u", "w", encoding="utf-8") as f:
            f.write(self.m3u_content)
        
        print("\nİşlem Tamamlandı! 'diziyou_playlist.json' ve 'diziyou_playlist.m3u' oluşturuldu.")

if __name__ == "__main__":
    scraper = DiziyouScraper()
    for series in TARGET_SERIES:
        scraper.scrape_series(series)
    scraper.save_files()
