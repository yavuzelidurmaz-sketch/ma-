import re
import json
import requests
import concurrent.futures

# Başlangıç noktası (Burası bizi güncel siteye atar)
ENTRY_POINT_URL = "https://www.selcuksportshd.is"

# Tarayıcı gibi görünmek için Headerlar
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7"
}

# Sabit Kanal Listesi (ID'ler genelde değişmez)
STATIC_CHANNELS = [
    {"name":"A Spor","logo_url":"/assets/images/channels/aspor.png","stream_url":"saspor","category":"futbol"},
    {"name":"ATV","logo_url":"/assets/images/channels/atv_logo.png","stream_url":"satv","category":"futbol"},
    {"name":"beIN Sports 1","logo_url":"/assets/images/channels/beinsports1.png","stream_url":"sbeinsports-1","category":"futbol"},
    {"name":"beIN Sports 2","logo_url":"/assets/images/channels/beinsports2.png","stream_url":"sbeinsports-2","category":"futbol"},
    {"name":"beIN Sports 3","logo_url":"/assets/images/channels/beinsports3.png","stream_url":"sbeinsports-3","category":"futbol"},
    {"name":"beIN Sports 4","logo_url":"/assets/images/channels/beinsports4.png","stream_url":"sbeinsports-4","category":"futbol"},
    {"name":"beIN Sports 5","logo_url":"/assets/images/channels/beinsports5.png","stream_url":"sbeinsports-5","category":"basketbol"},
    {"name":"beIN Sports Haber","logo_url":"/assets/images/channels/beinsportshaber.png","stream_url":"sbeinsportshaber","category":"futbol"},
    {"name":"Exxen Spor 1","logo_url":"/assets/images/channels/exxen.png","stream_url":"sexxen-1","category":"futbol"},
    {"name":"Exxen Spor 2","logo_url":"/assets/images/channels/exxen.png","stream_url":"sexxen-2","category":"futbol"},
    {"name":"Exxen Spor 3","logo_url":"/assets/images/channels/exxen.png","stream_url":"sexxen-3","category":"futbol"},
    {"name":"Exxen Spor 4","logo_url":"/assets/images/channels/exxen.png","stream_url":"sexxen-4","category":"futbol"},
    {"name":"Exxen Spor 5","logo_url":"/assets/images/channels/exxen.png","stream_url":"sexxen-5","category":"futbol"},
    {"name":"Exxen Spor 6","logo_url":"/assets/images/channels/exxen.png","stream_url":"sexxen-6","category":"futbol"},
    {"name":"S Sport","logo_url":"/assets/images/channels/ssport_logo.png","stream_url":"sssport","category":"futbol"},
    {"name":"S Sport 2","logo_url":"/assets/images/channels/ssport2_logo.png","stream_url":"sssport2","category":"futbol"},
    {"name":"S Sport Plus","logo_url":"/assets/images/channels/ssportplus_logo.png","stream_url":"sssplus1","category":"futbol"},
    {"name":"S Sport Plus 2","logo_url":"/assets/images/channels/ssportplus_logo.png","stream_url":"sssplus2","category":"futbol"},
    {"name":"Smart Spor","logo_url":"/assets/images/channels/smartspor.jpg","stream_url":"ssmartspor","category":"futbol"},
    {"name":"Tabii Spor 1","logo_url":"/assets/images/channels/tabiispor.png","stream_url":"stabiispor-1","category":"futbol"},
    {"name":"Tabii Spor 2","logo_url":"/assets/images/channels/tabiispor.png","stream_url":"stabiispor-2","category":"futbol"},
    {"name":"Tivibu Spor 1","logo_url":"/assets/images/channels/tivibu.png","stream_url":"stivibuspor-1","category":"futbol"},
    {"name":"Tivibu Spor 2","logo_url":"/assets/images/channels/tivibu.png","stream_url":"stivibuspor-2","category":"futbol"},
    {"name":"Tivibu Spor 3","logo_url":"/assets/images/channels/tivibu.png","stream_url":"stivibuspor-3","category":"futbol"},
    {"name":"Tivibu Spor 4","logo_url":"/assets/images/channels/tivibu.png","stream_url":"stivibuspor-4","category":"futbol"},
    {"name":"TRT 1","logo_url":"/assets/uploads/trt1-21284924-0-0-250-250.png","stream_url":"strt1","category":"futbol"},
    {"name":"TRT Spor","logo_url":"/assets/images/channels/trtspor.png","stream_url":"strtspor","category":"futbol"},
    {"name":"TV8","logo_url":"/assets/images/channels/tv8_logo.png","stream_url":"stv8","category":"futbol"}
]

def step1_find_current_site_domain():
    """1. ADIM: Giriş adresine gidip, yönlendirilen güncel site adresini bulur."""
    try:
        print(f"[*] ADIM 1: Güncel site aranıyor ({ENTRY_POINT_URL})...")
        session = requests.Session()
        response = session.get(ENTRY_POINT_URL, headers=HEADERS, timeout=20, allow_redirects=True)
        
        current_url = response.url
        if current_url.endswith('/'):
            current_url = current_url[:-1]
            
        print(f"[+] Güncel site bulundu: {current_url}")
        return current_url, response.text
    except Exception as e:
        print(f"[!] Hata (Adım 1): {e}")
        return None, None

def step2_extract_player_base_url(html_content, current_site_url):
    """2. ADIM: Ana sayfanın kaynak kodundan Player URL'sini (iframe src) söker."""
    print("[*] ADIM 2: Player URL'si taranıyor...")
    
    # Regex: src="https://...../index.php?id=" yapısını arar.
    # Bu regex iframe içindeki src'yi yakalar.
    match = re.search(r'src=["\'](https?://[^"\']+/index\.php\?id=)', html_content)
    
    if match:
        player_base = match.group(1)
        print(f"[+] Player URL bulundu: {player_base}")
        return player_base
    else:
        # Alternatif: Bazen iframe direkt html içinde değil JS içinde olabilir.
        # Bu durumda basit bir string araması yapalım.
        print("[!] Iframe regex ile bulunamadı, geniş arama yapılıyor...")
        match_alt = re.search(r'(https?://[^"\']+/index\.php\?id=)', html_content)
        if match_alt:
            player_base = match_alt.group(1)
            print(f"[+] Player URL bulundu (Alternatif): {player_base}")
            return player_base
            
        print("[!] Player URL ana sayfada bulunamadı!")
        return None

def step3_extract_stream_server_url(player_base_url, current_site_url):
    """3. ADIM: Player sayfasına gidip JS içindeki Stream Sunucu adresini (this.baseStreamUrl) bulur."""
    
    # Test için bir kanalı kullanıp player sayfasına gidiyoruz
    test_url = player_base_url + "sbeinsports-1"
    
    # Referer header'ı çok önemli, yoksa player açılmaz
    custom_headers = HEADERS.copy()
    custom_headers["Referer"] = current_site_url + "/"
    custom_headers["Origin"] = current_site_url

    try:
        print(f"[*] ADIM 3: Stream sunucusu çekiliyor ({test_url})...")
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
    if not channels:
        print("[!] Kaydedilecek kanal yok.")
        # Hata vermemesi için boş dosya
        with open("channels.json", "w") as f: f.write("[]")
        with open("playlist.m3u", "w") as f: f.write("#EXTM3U")
        return

    # 1. JSON
    with open("channels.json", "w", encoding="utf-8") as f:
        json.dump(channels, f, ensure_ascii=False, indent=4)
        
    # 2. M3U
    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        f.write(f'#EXTVLCOPT:http-referrer={current_domain}\n')
        
        for c in channels:
            name = c.get("name", "Unknown")
            logo = c.get("logo_url", "")
            if logo.startswith("/"):
                logo = current_domain + logo
            
            group = c.get("category", "General")
            url = c.get("final_url")
            
            f.write(f'#EXTINF:-1 tvg-logo="{logo}" group-title="{group}",{name}\n')
            f.write(f'#EXTVLCOPT:http-referrer={current_domain}\n')
            f.write(f'{url}\n')
            
    print(f"\n[*] {len(channels)} kanal başarıyla kaydedildi.")

def main():
    # ---------------------------------------------------------
    # ADIM 1: Güncel Siteyi Bul
    # ---------------------------------------------------------
    current_site_url, html_content = step1_find_current_site_domain()
    if not current_site_url:
        return

    # ---------------------------------------------------------
    # ADIM 2: O Sitedeki Güncel Player URL'sini Bul
    # ---------------------------------------------------------
    player_base_url = step2_extract_player_base_url(html_content, current_site_url)
    
    # Eğer player URL bulunamazsa manuel bir yedek (fallback) deneyebiliriz
    if not player_base_url:
        print("[!] Otomatik player tespiti başarısız. Varsayılan deneniyor...")
        player_base_url = "https://main.uxsyplayer8566224aa5.click/index.php?id="

    # ---------------------------------------------------------
    # ADIM 3: Player'ın İçindeki Güncel M3U8 Sunucusunu Bul
    # ---------------------------------------------------------
    stream_base_url = step3_extract_stream_server_url(player_base_url, current_site_url)
    
    if not stream_base_url:
        print("[!] KRİTİK: Yayın sunucusu bulunamadı.")
        # Boş dosya oluşturup çık
        with open("channels.json", "w") as f: f.write("[]")
        with open("playlist.m3u", "w") as f: f.write("#EXTM3U")
        return

    # Base URL '/' ile bitmeli
    if not stream_base_url.endswith('/'):
        stream_base_url += '/'

    # ---------------------------------------------------------
    # ADIM 4: Linkleri Oluştur ve Kaydet
    # ---------------------------------------------------------
    processed_channels = []
    print("[*] Linkler oluşturuluyor...")
    
    for channel in STATIC_CHANNELS:
        stream_id = channel.get("stream_url")
        if stream_id:
            # Final URL = StreamBase + ID + .m3u8
            final_url = f"{stream_base_url}{stream_id}/playlist.m3u8"
            
            channel["final_url"] = final_url
            channel["referer"] = current_site_url
            processed_channels.append(channel)

    save_outputs(processed_channels, current_site_url)

if __name__ == "__main__":
    main()
