import re
import json
import requests

# Giriş noktası (Buradan güncel siteyi ve sunucuyu öğreneceğiz)
ENTRY_POINT_URL = "https://www.selcuksportshd.is"

# Headerlar
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
}

# SENİN İÇİN TÜM KANALLARI BURAYA EKLEDİM (NFL, NBA, DAZN DAHİL)
ALL_CHANNELS = [
    # --- FUTBOL ---
    {"id": "saspor", "name": "A Spor", "cat": "Futbol"},
    {"id": "satv", "name": "ATV", "cat": "Futbol"},
    {"id": "stv8", "name": "TV8", "cat": "Futbol"},
    {"id": "sbeinsports-1", "name": "beIN Sports 1", "cat": "Futbol"},
    {"id": "sbeinsports-2", "name": "beIN Sports 2", "cat": "Futbol"},
    {"id": "sbeinsports-3", "name": "beIN Sports 3", "cat": "Futbol"},
    {"id": "sbeinsports-4", "name": "beIN Sports 4", "cat": "Futbol"},
    {"id": "sbeinsports-5", "name": "beIN Sports 5", "cat": "Basketbol"},
    {"id": "sbeinsportshaber", "name": "beIN Sports Haber", "cat": "Futbol"},
    {"id": "sexxen-1", "name": "Exxen Spor 1", "cat": "Futbol"},
    {"id": "sexxen-2", "name": "Exxen Spor 2", "cat": "Futbol"},
    {"id": "sexxen-3", "name": "Exxen Spor 3", "cat": "Futbol"},
    {"id": "sexxen-4", "name": "Exxen Spor 4", "cat": "Futbol"},
    {"id": "sexxen-5", "name": "Exxen Spor 5", "cat": "Futbol"},
    {"id": "sexxen-6", "name": "Exxen Spor 6", "cat": "Futbol"},
    {"id": "sssport", "name": "S Sport", "cat": "Futbol"},
    {"id": "sssport2", "name": "S Sport 2", "cat": "Futbol"},
    {"id": "sssplus1", "name": "S Sport Plus", "cat": "Futbol"},
    {"id": "sssplus2", "name": "S Sport Plus 2", "cat": "Futbol"},
    {"id": "ssmartspor", "name": "Smart Spor", "cat": "Futbol"},
    {"id": "ssmartspor2", "name": "Smart Spor 2", "cat": "Futbol"},
    {"id": "stabiispor-1", "name": "Tabii Spor 1", "cat": "Futbol"},
    {"id": "stabiispor-2", "name": "Tabii Spor 2", "cat": "Futbol"},
    {"id": "stabiispor-3", "name": "Tabii Spor 3", "cat": "Futbol"},
    {"id": "stabiispor-4", "name": "Tabii Spor 4", "cat": "Futbol"},
    {"id": "stabiispor-5", "name": "Tabii Spor 5", "cat": "Futbol"},
    {"id": "stivibuspor-1", "name": "Tivibu Spor 1", "cat": "Futbol"},
    {"id": "stivibuspor-2", "name": "Tivibu Spor 2", "cat": "Futbol"},
    {"id": "stivibuspor-3", "name": "Tivibu Spor 3", "cat": "Futbol"},
    {"id": "stivibuspor-4", "name": "Tivibu Spor 4", "cat": "Futbol"},
    {"id": "strt1", "name": "TRT 1", "cat": "Futbol"},
    {"id": "strtspor", "name": "TRT Spor", "cat": "Futbol"},
    {"id": "strtspor2", "name": "TRT Spor 2", "cat": "Futbol"},
    
    # --- YABANCI & DİĞER SPORLAR (NBA, NFL, DAZN, UFC) ---
    {"id": "sdazn1", "name": "DAZN 1", "cat": "UFC/Boks"},
    {"id": "sdazn2", "name": "DAZN 2", "cat": "UFC/Boks"},
    {"id": "nflnetwork", "name": "DAZN NFL Network", "cat": "NFL"},
    {"id": "nflchannel", "name": "NFL CHANNEL", "cat": "NFL"},
    {"id": "snbatv-1", "name": "NBA TV", "cat": "NBA"},
    {"id": "snbatv-2", "name": "NBA TV 2 (Yabancı)", "cat": "NBA"},
    {"id": "sufcfightpass", "name": "UFC Fight Pass", "cat": "UFC"},
    {"id": "seurosport1", "name": "EUROSPORT 1", "cat": "Genel"},
    {"id": "seurosport2", "name": "EUROSPORT 2", "cat": "Genel"},
    {"id": "smotorsporttv", "name": "Motorsport TV", "cat": "Motor Sporları"},
    {"id": "smotorvisiontv", "name": "Motorvision TV", "cat": "Motor Sporları"},
    {"id": "sskysportsf1de", "name": "Sky Sports F1 [DE]", "cat": "Formula 1"},
    {"id": "sskysportsf1ita", "name": "Sky Sports F1 [ITA]", "cat": "Formula 1"},
    {"id": "sskysportsf1uk", "name": "Sky Sports F1 [UK]", "cat": "Formula 1"},
]

def step1_find_current_site_domain():
    """1. ADIM: Giriş adresine gidip, yönlendirilen güncel site adresini bulur."""
    try:
        print(f"[*] ADIM 1: Güncel site aranıyor ({ENTRY_POINT_URL})...")
        session = requests.Session()
        response = session.get(ENTRY_POINT_URL, headers=HEADERS, timeout=20, allow_redirects=True)
        
        current_url = response.url
        # Sonundaki slash'ı temizle
        if current_url.endswith('/'):
            current_url = current_url[:-1]
            
        print(f"[+] Güncel site bulundu: {current_url}")
        return current_url, response.text
    except Exception as e:
        print(f"[!] Hata (Adım 1): {e}")
        return None, None

def step2_extract_player_base_url(html_content):
    """2. ADIM: HTML içinden Player URL'sini bulur."""
    if not html_content: return None
    
    # Iframe src regex
    match = re.search(r'src=["\'](https?://[^"\']+/index\.php\?id=)', html_content)
    if match:
        return match.group(1)
        
    # Yedek arama
    match_alt = re.search(r'(https?://[^"\']+/index\.php\?id=)', html_content)
    if match_alt:
        return match_alt.group(1)
            
    # Eğer bulamazsa varsayılanı döndür (Genelde bu çalışır)
    print("[!] Player URL bulunamadı, varsayılan deneniyor.")
    return "https://main.uxsyplayer8566224aa5.click/index.php?id="

def step3_extract_stream_server_url(player_base_url, current_site_url):
    """3. ADIM: Player içinden güncel yayın sunucusunu (dga1op... gibi) bulur."""
    
    # Test için beIN 1'i kullanalım
    test_url = player_base_url + "sbeinsports-1"
    
    custom_headers = HEADERS.copy()
    custom_headers["Referer"] = current_site_url + "/"
    custom_headers["Origin"] = current_site_url

    try:
        print(f"[*] ADIM 3: Yayın sunucusu tespit ediliyor...")
        res = requests.get(test_url, headers=custom_headers, timeout=15)
        
        # JS içindeki this.baseStreamUrl = '...' kısmını yakala
        match = re.search(r"this\.baseStreamUrl\s*=\s*['\"]([^'\"]+)['\"]", res.text)
        
        if match:
            stream_base = match.group(1)
            print(f"[+] STREAM SUNUCUSU BULUNDU: {stream_base}")
            return stream_base
        else:
            print("[!] Stream Base URL regex ile bulunamadı.")
            return None
            
    except Exception as e:
        print(f"[!] Hata (Adım 3): {e}")
        return None

def save_outputs(channels, current_domain):
    """Dosyaları kaydeder."""
    
    # 1. JSON
    with open("channels.json", "w", encoding="utf-8") as f:
        json.dump(channels, f, ensure_ascii=False, indent=4)
        
    # 2. M3U
    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        f.write(f'#EXTVLCOPT:http-referrer={current_domain}\n')
        f.write(f'#EXTVLCOPT:http-user-agent={HEADERS["User-Agent"]}\n')
        
        for c in channels:
            name = c.get("name")
            group = c.get("category")
            url = c.get("final_url")
            # Logo url, basitçe site domaini + path
            logo = f"{current_domain}/assets/images/channels/{c.get('stream_url')}.png" 
            
            f.write(f'#EXTINF:-1 tvg-logo="{logo}" group-title="{group}",{name}\n')
            f.write(f'#EXTVLCOPT:http-referrer={current_domain}\n')
            f.write(f'{url}\n')
            
    print(f"\n[*] Toplam {len(channels)} kanal başarıyla kaydedildi.")

def main():
    # 1. Siteyi Bul
    current_site_url, html_content = step1_find_current_site_domain()
    if not current_site_url:
        # Siteye hiç ulaşamazsa çıkma, default ile dene
        current_site_url = "https://www.selcuksportshd.xyz"

    # 2. Player Adresini Bul
    player_base_url = step2_extract_player_base_url(html_content)

    # 3. Yayın Sunucusunu Bul (Burası kritik)
    stream_base_url = step3_extract_stream_server_url(player_base_url, current_site_url)
    
    if not stream_base_url:
        print("[!] Kritik hata: Yayın sunucusu bulunamadı. Boş dosya oluşuyor.")
        with open("channels.json", "w") as f: f.write("[]")
        with open("playlist.m3u", "w") as f: f.write("#EXTM3U")
        return

    # Slash kontrolü
    if not stream_base_url.endswith('/'):
        stream_base_url += '/'

    # 4. Linkleri Oluştur (Manuel liste üzerinden)
    print("[*] Linkler oluşturuluyor...")
    
    processed_channels = []
    
    for channel_info in ALL_CHANNELS:
        stream_id = channel_info["id"]
        
        # Link oluştur: Sunucu + ID + .m3u8
        # Örn: https://dga1.../live/nflchannel/playlist.m3u8
        final_url = f"{stream_base_url}{stream_id}/playlist.m3u8"
        
        # JSON objesini hazırla
        processed_data = {
            "name": channel_info["name"],
            "stream_url": stream_id,
            "category": channel_info["cat"],
            "final_url": final_url,
            "referer": current_site_url
        }
        processed_channels.append(processed_data)

    # 5. Kaydet
    save_outputs(processed_channels, current_site_url)

if __name__ == "__main__":
    main()
