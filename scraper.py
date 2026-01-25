import re
import json
import requests
import concurrent.futures
from urllib.parse import urljoin

# Hedef site bilgileri (HTML'den çıkarılan base URL'ler)
BASE_URL = "https://www.sporcafe.xyz"  # Veya güncel domain neyse
# HTML kodundaki iframe prefix'i
PLAYER_BASE_URL = "https://main.uxsyplayer8566224aa5.click/index.php?id="

# Tarayıcı gibi görünmek için Headerlar (Engellenmemek için şart)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": BASE_URL,
    "Origin": BASE_URL
}

def get_channels_data():
    """Ana sayfadan JSON verisini çeker."""
    try:
        print(f"[*] Ana sayfa taranıyor: {BASE_URL}")
        response = requests.get(BASE_URL, headers=HEADERS, timeout=15)
        response.raise_for_status()
        
        # HTML içindeki 'const channelsData = [...]' kısmını regex ile bul
        match = re.search(r'const channelsData\s*=\s*(\[.*?\]);', response.text, re.DOTALL)
        
        if match:
            json_str = match.group(1)
            # JSON formatını Python listesine çevir
            data = json.loads(json_str)
            print(f"[*] Toplam {len(data)} kanal bulundu.")
            return data
        else:
            print("[!] Kanal verisi (channelsData) bulunamadı.")
            return []
    except Exception as e:
        print(f"[!] Hata oluştu: {e}")
        return []

def resolve_stream_url(channel):
    """Her kanal için player sayfasına gidip gerçek .m3u8 linkini bulur."""
    stream_id = channel.get("stream_url")
    if not stream_id:
        return None

    # HTML'deki mantık: mainIframeUrl + id
    player_url = f"{PLAYER_BASE_URL}{stream_id}"
    
    try:
        # Player sayfasına istek at (Referer önemli)
        res = requests.get(player_url, headers=HEADERS, timeout=10)
        
        # Player sayfasındaki .m3u8 linkini regex ile ara
        # Genelde: file: "http...", source: "http..." veya direkt string içinde olur.
        # Bu regex 'http' ile başlayıp '.m3u8' ile biten stringleri yakalar.
        m3u8_match = re.search(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', res.text)
        
        if m3u8_match:
            real_url = m3u8_match.group(1)
            
            # Link bazen ters slash (\/) ile gelebilir, düzeltelim
            real_url = real_url.replace('\\/', '/')
            
            # Kanal objesine ekle
            channel["final_url"] = real_url
            print(f"[+] Link bulundu: {channel['name']} -> {real_url[:30]}...")
            return channel
        else:
            print(f"[-] Link bulunamadı: {channel['name']} ({stream_id})")
            return None
            
    except Exception as e:
        print(f"[!] Player hatası ({channel['name']}): {e}")
        return None

def save_outputs(channels):
    """M3U ve JSON dosyalarını oluşturur."""
    valid_channels = [c for c in channels if c is not None and "final_url" in c]
    
    # 1. JSON Çıktısı
    with open("channels.json", "w", encoding="utf-8") as f:
        json.dump(valid_channels, f, ensure_ascii=False, indent=4)
        
    # 2. M3U Çıktısı
    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for c in valid_channels:
            name = c.get("name", "Unknown")
            logo = c.get("logo_url", "")
            group = c.get("category", "General")
            url = c.get("final_url")
            
            # Logo URL'si tam değilse tamamla (HTML'de /assets/... diye başlıyor)
            if logo.startswith("/"):
                logo = BASE_URL + logo
                
            f.write(f'#EXTINF:-1 tvg-logo="{logo}" group-title="{group}",{name}\n')
            f.write(f'{url}\n')
            
    print(f"\n[OK] İşlem tamamlandı. {len(valid_channels)} kanal kaydedildi.")

def main():
    raw_channels = get_channels_data()
    
    if not raw_channels:
        return

    processed_channels = []
    
    # Çoklu iş parçacığı (Threading) ile hızlandırma (Aynı anda 10 kanal tara)
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(resolve_stream_url, raw_channels)
        
        for result in results:
            if result:
                processed_channels.append(result)
                
    save_outputs(processed_channels)

if __name__ == "__main__":
    main()
