import requests
from bs4 import BeautifulSoup
import json
import re
import os
import time

# Ayarlar
BASE_URL = "https://www.filmmodu.ws"
ARCHIVE_URL = "https://www.filmmodu.ws/arsiv-filmler"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Referer": "https://www.filmmodu.ws/"
}

def get_soup(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        return BeautifulSoup(response.content, 'html.parser')
    except Exception as e:
        print(f"Hata oluştu ({url}): {e}")
        return None

def extract_m3u8_from_html(html_content):
    """
    HTML içeriğinde gizlenmiş m3u8 veya mp4 linklerini arar.
    Not: Site blob veya şifreli JS kullanıyorsa bu yöntem çalışmayabilir.
    """
    # Basit regex ile .m3u8 veya .mp4 arama
    regex = r'(https?://[^\s"\']+\.(?:m3u8|mp4))'
    matches = re.findall(regex, str(html_content))
    if matches:
        return matches[0] # İlk bulunan linki döndür
    return None

def scrape_movies():
    soup = get_soup(ARCHIVE_URL)
    if not soup:
        return []

    movies_data = []
    
    # Film kartlarını bul (filmmoduana.txt analizine göre)
    movie_cards = soup.select('.row.movie-list .movie')
    
    print(f"Toplam {len(movie_cards)} film bulundu. İşleniyor...")

    for card in movie_cards:
        try:
            # 1. Temel Bilgileri Al
            title_tag = card.select_one('.detail .original-name')
            tr_title_tag = card.select_one('.detail .turkish-name')
            
            title = title_tag.text.strip() if title_tag else "Bilinmeyen Başlık"
            if tr_title_tag and tr_title_tag.text.strip():
                title = f"{title} ({tr_title_tag.text.strip()})"
            
            # Linki al
            link_tag = card.find('a')
            movie_page_url = link_tag['href'] if link_tag else None
            
            # Posteri al (Lazy load olduğu için data-src kontrolü)
            img_tag = card.select_one('img')
            poster = ""
            if img_tag:
                poster = img_tag.get('data-src') or img_tag.get('src')
            
            if not movie_page_url:
                continue

            # Tam URL oluştur
            if not movie_page_url.startswith('http'):
                movie_page_url = BASE_URL + movie_page_url

            print(f"Film taranıyor: {title}")

            # 2. Film Sayfasına Git (Detaylar ve Kaynaklar için)
            detail_soup = get_soup(movie_page_url)
            if not detail_soup:
                continue

            # Dil seçeneklerini (Altyazı/Dublaj) bul
            # filmmoduv.txt analizine göre butonlar .alternates .btn-group içinde
            sources = []
            
            # Mevcut sayfanın kendisi bir kaynaktır (Genellikle Altyazılı başlar)
            # Sayfa içindeki video kaynağını aramayı dene
            direct_video_url = extract_m3u8_from_html(detail_soup)
            
            # Sayfadaki diğer dil seçenekleri butonlarını bul
            buttons = detail_soup.select('.alternates .btn-group a')
            
            # Eğer hiç buton yoksa, sadece mevcut sayfayı ekle
            if not buttons:
                 sources.append({
                    "label": "Varsayılan",
                    "url": direct_video_url if direct_video_url else movie_page_url,
                    "is_direct": bool(direct_video_url)
                })

            for btn in buttons:
                btn_text = btn.text.strip()
                btn_href = btn['href']
                
                if not btn_href.startswith('http'):
                    btn_href = BASE_URL + btn_href

                # Link türünü belirle
                label = "Bilinmeyen"
                if "Altyazı" in btn_text:
                    label = "TR Altyazılı"
                elif "Dublaj" in btn_text:
                    label = "TR Dublaj"
                elif "Fragman" in btn_text:
                    continue # Fragmanları atla

                # Not: Gerçek bir senaryoda her dil seçeneği için o sayfaya gidip
                # m3u8 çekmek gerekir. Performans için şimdilik sayfa linkini ekliyoruz.
                # Eğer script o sayfaya gidip m3u8 arasın isterseniz buraya bir get_soup daha eklenir.
                
                sources.append({
                    "label": label,
                    "url": btn_href, # Eğer m3u8 bulamazsa sayfa linkini koyar
                    "is_direct": False 
                })

            # Filmi listeye ekle
            movies_data.append({
                "title": title,
                "poster": poster,
                "sources": sources
            })
            
            # Sunucuyu yormamak için kısa bekleme
            time.sleep(0.5)

        except Exception as e:
            print(f"Film işlenirken hata: {e}")
            continue

    return movies_data

def save_to_json(data, filename="filmler.json"):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print(f"{filename} oluşturuldu.")

def save_to_m3u(data, filename="playlist.m3u"):
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        for movie in data:
            for source in movie['sources']:
                # M3U Formatı
                # #EXTINF:-1 tvg-logo="POSTER_URL" group-title="KATEGORI", BASLIK
                # URL
                title_full = f"{movie['title']} [{source['label']}]"
                f.write(f'#EXTINF:-1 tvg-logo="{movie["poster"]}" group-title="FilmModu", {title_full}\n')
                f.write(f'{source["url"]}\n')
    print(f"{filename} oluşturuldu.")

def main():
    print("Scraping işlemi başlatılıyor...")
    data = scrape_movies()
    
    if data:
        save_to_json(data)
        save_to_m3u(data)
        print("İşlem tamamlandı.")
    else:
        print("Veri çekilemedi.")

if __name__ == "__main__":
    main()
