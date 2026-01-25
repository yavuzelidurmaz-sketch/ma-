import re
import json
import requests

# Başlangıç noktası
ENTRY_POINT_URL = "https://www.selcuksportshd.is"

# Tarayıcı Headerları
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7"
}

def step1_get_site_and_channels():
    """1. ADIM: Güncel siteye gider ve sitedeki TÜM kanal listesini (JSON) çeker."""
    try:
        print(f"[*] ADIM 1: Güncel site ve kanal listesi aranıyor...")
        session = requests.Session()
        response = session.get(ENTRY_POINT_URL, headers=HEADERS, timeout=20, allow_redirects=True)
        response.raise_for_status()
        
        current_url = response.url
        if current_url.endswith('/'):
            current_url = current_url[:-1]
            
        print(f"[+] Güncel site bulundu: {current_url}")
        
        # Sitenin içindeki 'const channelsData = [...]' verisini çekiyoruz
        # Bu veri sitedeki TÜM kanalları (NFL, NBA, DAZN vb.) içerir.
        match = re.search(r'const channelsData\s*=\s*(\[.*?\]);', response.text, re.DOTALL)
        
        channels = []
        if match:
            try:
                json_str = match.group(1)
                channels = json.loads(json_str)
                print(f"[+] Siteden {len(channels)} adet kanal verisi çekildi (NBA, NFL, DAZN dahil).")
            except json.JSONDecodeError:
                print("[!] Kanal verisi JSON formatında değil.")
        else:
            print("[!] Kanal verisi (channelsData) sayfada bulunamadı.")

        return current_url, response.text, channels

    except Exception as e:
        print(f"[!] Hata (Adım 1): {e}")
        return None, None, []

def step2_extract_player_base_url(html_content):
    """2. ADIM: Player URL'sini bulur."""
    if not html_content: return None
    
    # Iframe src'sini bul
    match = re.search(r'src=["\'](https?://[^"\']+/index\.php\?id=)', html_content)
    
    if match:
        return match.group(1)
    
    # Alternatif arama
    match_alt = re.search(r'(https?://[^"\']+/index\.php\?id=)', html_content)
    if match_alt:
        return match_alt.group(1)
            
    return "https://main.uxsyplayer8566224aa5.click/index.php?id=" # Varsayılan

def step3_extract_stream_server_url(player_base_url, current_site_url):
    """3. ADIM: Player içinden güncel yayın sunucusunu (dga1op... gibi) bulur."""
    
    # Test için bir ID kullanıyoruz (NFL kanalı var mı kontrol edelim)
    test_url = player_base_url + "nflchannel" 
    
    custom_headers = HEADERS.copy()
    custom_headers["Referer"] = current_site_url + "/"
    custom_headers["Origin"] = current_site_url

    try:
        print(f"[*] ADIM 3: Yayın sunucusu tespit ediliyor...")
        res = requests.get(test_url, headers=custom_headers, timeout=15)
        
        match = re.search(r"this\.baseStreamUrl\s*=\s*['\"]([^'\"]+)['\"]", res.text)
        
        if match:
            stream_base = match.group(1)
            print(f"[+] STREAM SUNUCUSU BULUNDU: {stream_base}")
            return stream_base
        else:
            print("[!] Stream Base URL bulunamadı.")
            return None
            
    except Exception as e:
        print(f"[!] Hata (Adım 3): {e}")
        return None

def save_outputs(channels, current_domain):
    """Dosyaları kaydeder."""
    if not channels:
        print("[!] Kaydedilecek kanal yok.")
        return

    # 1. JSON
    with open("channels.json", "w", encoding="utf-8") as f:
        json.dump(channels, f, ensure_ascii=False, indent=4)
        
    # 2. M3U
    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        f.write(f'#EXTVLCOPT:http-referrer={current_domain}\n')
        
        # Linkleri oluştururken tekrar edenleri (duplicate) engellemek için set kullanalım
        seen_urls = set()

        for c in channels:
            name = c.get("name", "Unknown")
            logo = c.get("logo_url", "")
            # Logo linkini tam yap
            if logo.startswith("/"):
                logo = current_domain + logo
            
            group = c.get("category", "General").upper() # Kategoriyi büyük harf yap (FUTBOL, NBA)
            url = c.get("final_url")
            
            # Eğer bu linki daha önce yazmadıysak dosyaya ekle
            if url and url not in seen_urls:
                f.write(f'#EXTINF:-1 tvg-logo="{logo}" group-title="{group}",{name}\n')
                f.write(f'#EXTVLCOPT:http-referrer={current_domain}\n')
                f.write(f'{url}\n')
                seen_urls.add(url)
            
    print(f"\n[*] Toplam {len(seen_urls)} benzersiz kanal kaydedildi.")

def main():
    # 1. Siteye git ve TÜM kanal listesini çal
    current_site_url, html_content, dynamic_channels = step1_get_site_and_channels()
    
    if not current_site_url:
        return

    # Eğer siteden veri çekilemediyse (site yapısı değiştiyse), script durmasın diye boş liste uyarısı
    if not dynamic_channels:
        print("[!] Siteden kanal listesi çekilemedi! Manuel liste kullanılamıyor.")
        return

    # 2. Player adresini bul
    player_base_url = step2_extract_player_base_url(html_content)

    # 3. Yayın sunucusunu bul (dga1op...click vb.)
    stream_base_url = step3_extract_stream_server_url(player_base_url, current_site_url)
    
    if not stream_base_url:
        print("[!] Yayın sunucusu bulunamadı.")
        return

    if not stream_base_url.endswith('/'):
        stream_base_url += '/'

    # 4. Linkleri oluştur
    print("[*] Tüm kanallar için linkler oluşturuluyor...")
    
    processed_channels = []
    
    for channel in dynamic_channels:
        # JSON verisindeki 'stream_url' anahtarını al (örn: 'nflchannel', 'sdazn1')
        stream_id = channel.get("stream_url")
        
        if stream_id:
            # Link oluşturma: Sunucu + ID + .m3u8
            # Örn: https://dga1...click/live/nflchannel/playlist.m3u8
            final_url = f"{stream_base_url}{stream_id}/playlist.m3u8"
            
            channel["final_url"] = final_url
            channel["referer"] = current_site_url
            processed_channels.append(channel)

    # 5. Kaydet
    save_outputs(processed_channels, current_site_url)

if __name__ == "__main__":
    main()
