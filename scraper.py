import re
import json
import requests
import concurrent.futures

# Oynatıcı adresi
PLAYER_BASE_URL = "https://main.uxsyplayer8566224aa5.click/index.php?id="

# Headerlar
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.sporcafe.xyz/",
    "Origin": "https://www.sporcafe.xyz"
}

# Senin verdiğin sabit kanal listesi
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

def get_base_stream_url():
    """Herhangi bir player sayfasına gidip güncel Base URL'i (dga1op10...) çeker."""
    test_url = PLAYER_BASE_URL + "sbeinsports-1"
    try:
        print("[*] Güncel yayın sunucusu (Base URL) tespit ediliyor...")
        res = requests.get(test_url, headers=HEADERS, timeout=10)
        
        # JS içindeki this.baseStreamUrl = '...' kısmını yakala
        match = re.search(r"this\.baseStreamUrl\s*=\s*['\"]([^'\"]+)['\"]", res.text)
        
        if match:
            base_url = match.group(1)
            print(f"[+] Base URL bulundu: {base_url}")
            return base_url
        else:
            print("[!] Base URL regex ile bulunamadı!")
            return None
    except Exception as e:
        print(f"[!] Base URL çekilirken hata: {e}")
        return None

def resolve_stream_url(channel, base_url):
    """Bulunan Base URL ile kanal linkini oluşturur."""
    stream_id = channel.get("stream_url")
    if not stream_id or not base_url:
        return None

    # JS kodundaki mantık: baseStreamUrl + streamId + /playlist.m3u8
    # Örn: https://dga1.../live/ + sbeinsports-1 + /playlist.m3u8
    
    # Base URL genelde '/' ile biter ama kontrol edelim
    if not base_url.endswith('/'):
        base_url += '/'
        
    final_url = f"{base_url}{stream_id}/playlist.m3u8"
    
    channel["final_url"] = final_url
    print(f"[+] Oluşturuldu: {channel['name']}")
    return channel

def save_outputs(channels):
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
        for c in channels:
            name = c.get("name", "Unknown")
            logo = c.get("logo_url", "")
            # Logo URL tamamlama
            if logo.startswith("/"):
                # Ana site URL'i ekleyelim ki logolar görünsün
                logo = "https://www.sporcafe.xyz" + logo
            
            group = c.get("category", "General")
            url = c.get("final_url")
            
            f.write(f'#EXTINF:-1 tvg-logo="{logo}" group-title="{group}",{name}\n')
            f.write(f'{url}\n')
            
    print(f"\n[*] {len(channels)} kanal başarıyla kaydedildi.")

def main():
    # 1. Önce Base URL'i bul (Tek bir istek atarak)
    base_url = get_base_stream_url()
    
    if not base_url:
        print("[!] Base URL bulunamadığı için işlem iptal edildi.")
        # Boş dosya oluştur ki Action hata vermesin
        with open("channels.json", "w") as f: f.write("[]")
        with open("playlist.m3u", "w") as f: f.write("#EXTM3U")
        return

    processed_channels = []
    
    # 2. Base URL'i kullanarak tüm linkleri oluştur (Hızlıca)
    # Artık her siteye istek atmamıza gerek yok, string birleştiriyoruz.
    for channel in STATIC_CHANNELS:
        result = resolve_stream_url(channel, base_url)
        if result:
            processed_channels.append(result)
                
    save_outputs(processed_channels)

if __name__ == "__main__":
    main()
