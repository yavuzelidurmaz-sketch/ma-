import re
import json
import requests
import concurrent.futures
import os

# Hedef site bilgileri
BASE_URL = "https://www.sporcafe.xyz" 
PLAYER_BASE_URL = "https://main.uxsyplayer8566224aa5.click/index.php?id="

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": BASE_URL,
    "Origin": BASE_URL,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7"
}

def get_channels_data():
    """Ana sayfadan JSON verisini çeker."""
    try:
        print(f"[*] Ana sayfa taranıyor: {BASE_URL}")
        session = requests.Session()
        response = session.get(BASE_URL, headers=HEADERS, timeout=20)
        
        # Debug: Durum kodunu yazdır
        print(f"[*] HTTP Status: {response.status_code}")
        
        response.raise_for_status()
        
        # HTML içindeki 'const channelsData = [...]' kısmını regex ile bul
        match = re.search(r'const channelsData\s*=\s*(\[.*?\]);', response.text, re.DOTALL)
        
        if match:
            json_str = match.group(1)
            data = json.loads(json_str)
            print(f"[*] Toplam {len(data)} kanal bulundu.")
            return data
        else:
            print("[!] Kanal verisi (channelsData) bulunamadı.")
            # Debug: Eğer bulamazsa HTML'in ilk 500 karakterini bas ki ne döndüğünü görelim
            print(f"[DEBUG] Gelen HTML başı: {response.text[:500]}")
            return []
    except Exception as e:
        print(f"[!] Ana sayfa hatası: {e}")
        return []

def resolve_stream_url(channel):
    """Her kanal için player sayfasına gidip gerçek .m3u8 linkini bulur."""
    stream_id = channel.get("stream_url")
    if not stream_id:
        return None

    player_url = f"{PLAYER_BASE_URL}{stream_id}"
    
    try:
        res = requests.get(player_url, headers=HEADERS, timeout=10)
        m3u8_match = re.search(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', res.text)
        
        if m3u8_match:
            real_url = m3u8_match.group(1).replace('\\/', '/')
            channel["final_url"] = real_url
            # print(f"[+] Link bulundu: {channel['name']}") # Log kirliliği yapmasın diye kapattım
            return channel
        else:
            return None
            
    except Exception:
        return None

def save_outputs(channels):
    """M3U ve JSON dosyalarını oluşturur (Boş olsa bile)."""
    
    # Veri olmasa bile boş liste ile devam et
    valid_channels = [c for c in channels if c is not None and "final_url" in c] if channels else []
    
    print(f"[*] Kaydedilecek geçerli kanal sayısı: {len(valid_channels)}")

    # 1. JSON Çıktısı
    with open("channels.json", "w", encoding="utf-8") as f:
        json.dump(valid_channels, f, ensure_ascii=False, indent=4)
        
    # 2. M3U Çıktısı
    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for c in valid_channels:
            name = c.get("name", "Unknown")
            logo = c.get("logo_url", "")
            if logo.startswith("/"):
                logo = BASE_URL + logo
            group = c.get("category", "General")
            url = c.get("final_url")
            
            f.write(f'#EXTINF:-1 tvg-logo="{logo}" group-title="{group}",{name}\n')
            f.write(f'{url}\n')

def main():
    raw_channels = get_channels_data()
    
    processed_channels = []
    
    if raw_channels:
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            results = executor.map(resolve_stream_url, raw_channels)
            for result in results:
                if result:
                    processed_channels.append(result)
    else:
        print("[!] Hiç kanal bulunamadı, boş dosyalar oluşturuluyor...")

    # save_outputs fonksiyonunu her durumda çağırıyoruz
    save_outputs(processed_channels)

if __name__ == "__main__":
    main()
