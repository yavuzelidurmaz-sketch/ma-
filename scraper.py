import re
import json
import requests
import concurrent.futures
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# Hedef site bilgileri
BASE_URL = "https://www.sporcafe.xyz" 
PLAYER_BASE_URL = "https://main.uxsyplayer8566224aa5.click/index.php?id="

# Requests için Headerlar (Stream linklerini çözerken lazım)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": BASE_URL,
    "Origin": BASE_URL
}

def get_channels_with_selenium():
    """Ana sayfayı gerçek bir tarayıcı gibi açıp veriyi çeker."""
    print(f"[*] Selenium ile ana sayfaya gidiliyor: {BASE_URL}")
    
    # Chrome Ayarları (Headless - Arayüzsüz Mod)
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Ekransız çalıştır
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    driver = None
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        driver.get(BASE_URL)
        time.sleep(5)  # Sitenin yüklenmesi ve JS'lerin çalışması için bekle
        
        page_source = driver.page_source
        
        # HTML içindeki veriyi ara
        match = re.search(r'const channelsData\s*=\s*(\[.*?\]);', page_source, re.DOTALL)
        
        if match:
            json_str = match.group(1)
            data = json.loads(json_str)
            print(f"[*] Başarılı! {len(data)} kanal bulundu.")
            return data
        else:
            print("[!] Selenium sayfayı açtı ama 'channelsData' verisini bulamadı.")
            # Debug: HTML'in bir kısmını yazdıralım
            print(f"[DEBUG] HTML Özeti: {page_source[:500]}")
            return []
            
    except Exception as e:
        print(f"[!] Selenium Hatası: {e}")
        return []
    finally:
        if driver:
            driver.quit()

def resolve_stream_url(channel):
    """Her kanal için player sayfasına gidip gerçek .m3u8 linkini bulur."""
    stream_id = channel.get("stream_url")
    if not stream_id:
        return None

    player_url = f"{PLAYER_BASE_URL}{stream_id}"
    
    try:
        # Burası için hala requests kullanabiliriz, daha hızlıdır.
        # Eğer burası da engellenirse burayı da Selenium'a çevirebiliriz ama yavaşlatır.
        res = requests.get(player_url, headers=HEADERS, timeout=10)
        
        # Link bazen JS içinde gizli olabilir, basit regex ile arıyoruz
        m3u8_match = re.search(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', res.text)
        
        if m3u8_match:
            real_url = m3u8_match.group(1).replace('\\/', '/')
            channel["final_url"] = real_url
            print(f"[+] Link Çözüldü: {channel['name']}")
            return channel
        else:
            # print(f"[-] Link Bulunamadı: {channel['name']}")
            return None
            
    except Exception:
        return None

def save_outputs(channels):
    """M3U ve JSON dosyalarını oluşturur."""
    valid_channels = [c for c in channels if c is not None and "final_url" in c] if channels else []
    
    print(f"[*] Toplam {len(valid_channels)} çalışan kanal kaydediliyor.")

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
    # 1. Adım: Ana listeyi Selenium ile al
    raw_channels = get_channels_with_selenium()
    
    processed_channels = []
    
    # 2. Adım: Linkleri çöz (Hız için Threading kullanıyoruz)
    if raw_channels:
        print("[*] Linkler çözülüyor (Bu işlem biraz sürebilir)...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            results = executor.map(resolve_stream_url, raw_channels)
            for result in results:
                if result:
                    processed_channels.append(result)
    else:
        print("[!] Liste boş geldiği için link çözme işlemi atlandı.")

    save_outputs(processed_channels)

if __name__ == "__main__":
    main()
