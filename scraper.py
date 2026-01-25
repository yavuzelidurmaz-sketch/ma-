import re
import json
import requests
import concurrent.futures

# Oynatıcı adresi (HTML'den alındı)
PLAYER_BASE_URL = "https://main.uxsyplayer8566224aa5.click/index.php?id="

# Headerlar: Sanki site üzerinden izliyormuşuz gibi görünmek için
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.sporcafe.xyz/",
    "Origin": "https://www.sporcafe.xyz"
}

# İlk mesajındaki kanal listesini buraya gömdük
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

def resolve_stream_url(channel):
    """Player sayfasına gidip gerçek linki çeker."""
    stream_id = channel.get("stream_url")
    if not stream_id:
        return None

    player_url = f"{PLAYER_BASE_URL}{stream_id}"
    
    try:
        # Timeout'u kısa tutalım ki hızlı geçsin
        res = requests.get(player_url, headers=HEADERS, timeout=10)
        
        # .m3u8 linkini regex ile bul
        m3u8_match = re.search(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', res.text)
        
        if m3u8_match:
            real_url = m3u8_match.group(1).replace('\\/', '/')
            channel["final_url"] = real_url
            print(f"[+] {channel['name']} -> OK")
            return channel
        else:
            print(f"[-] {channel['name']} -> Link bulunamadı (Stream ID: {stream_id})")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"[!] Hata ({channel['name']}): Erişim sorunu.")
        return None

def save_outputs(channels):
    """JSON ve M3U dosyalarını kaydeder."""
    if not channels:
        print("[!] Hiçbir kanal çözülemedi.")
        # Yine de boş dosya oluştur ki Git hata vermesin
        with open("channels.json", "w") as f: f.write("[]")
        with open("playlist.m3u", "w") as f: f.write("#EXTM3U")
        return

    # 1. JSON
    with open("channels.json", "w", encoding="utf-8") as f:
        json.dump(channels, f, ensure_ascii=False, indent=4)
        
    # 2. M3U
    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for c in channels:
            name = c.get("name", "Unknown")
            # Logo URL'si tam değilse düzelt (Görsel için domain gerekebilir ama opsiyonel)
            logo = c.get("logo_url", "") 
            group = c.get("category", "General")
            url = c.get("final_url")
            
            f.write(f'#EXTINF:-1 tvg-logo="{logo}" group-title="{group}",{name}\n')
            f.write(f'{url}\n')
            
    print(f"\n[*] Başarılı: {len(channels)} kanal dosyaya yazıldı.")

def main():
    print(f"[*] İşlem başlıyor. {len(STATIC_CHANNELS)} kanal taranacak...")
    
    processed_channels = []
    
    # Hızlı tarama için Threading
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        results = executor.map(resolve_stream_url, STATIC_CHANNELS)
        
        for result in results:
            if result:
                processed_channels.append(result)
                
    save_outputs(processed_channels)

if __name__ == "__main__":
    main()
