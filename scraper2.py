import re
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# En son bildiğimiz numara (Buradan başlayıp ileriye doğru arayacak)
LAST_KNOWN_NUMBER = 1514
DOMAIN_EXTENSION = ".xyz" # Genelde .xyz kullanıyorlar

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Referer": "https://www.google.com/"
}

def find_active_domain():
    """
    Sırayla domainleri dener (1514, 1515, 1516...)
    Çalışan ilk siteyi bulur ve döndürür.
    """
    print("[*] ADIM 1: Güncel TRGoals adresi taranıyor...")
    
    # 20 ileriye kadar dene (Gerekirse artırılabilir)
    for i in range(0, 20):
        current_num = LAST_KNOWN_NUMBER + i
        candidate_url = f"https://trgoals{current_num}{DOMAIN_EXTENSION}/"
        
        try:
            print(f"   > Deneniyor: {candidate_url}")
            res = requests.get(candidate_url, headers=HEADERS, timeout=5)
            
            # Eğer site açıldıysa ve içinde 'TRGoals' yazısı varsa doğrudur
            if res.status_code == 200 and "TRGoals" in res.text:
                print(f"[+] AKTİF SİTE BULUNDU: {candidate_url}")
                return candidate_url, res.text
                
        except requests.exceptions.RequestException:
            # Site kapalıysa pas geç
            continue
            
    print("[!] Hata: Hiçbir domain çalışmıyor. Sayı aralığı değişmiş olabilir.")
    return None, None

def step2_parse_channels(html_content, base_url):
    """HTML içinden maçları toplar."""
    print("[*] ADIM 2: Maç listesi oluşturuluyor...")
    
    soup = BeautifulSoup(html_content, 'html.parser')
    channels = []
    
    # <a class="channel-item"> elemanlarını bul
    items = soup.find_all('a', class_='channel-item')
    
    for item in items:
        try:
            href = item.get('href')
            if not href or 'id=' not in href: continue
            
            stream_id = href.split('id=')[1]
            
            # Kategori
            cat_raw = item.get('data-category', 'other')
            category = "Genel"
            if cat_raw == 'football': category = "Futbol"
            elif cat_raw == 'basketball': category = "Basketbol"
            elif cat_raw == '24-7': category = "7/24 TV"
            
            # İsim
            name_div = item.find('div', class_='channel-name')
            channel_name = name_div.get_text(strip=True) if name_div else f"Kanal {stream_id}"
            
            channels.append({
                "id": stream_id,
                "name": channel_name,
                "category": category,
                "href": href
            })
            
        except Exception: continue
        
    print(f"[+] {len(channels)} adet maç/kanal listeye eklendi.")
    return channels

def step3_find_stream_server_recursive(current_domain, sample_channel):
    """
    Yayın sayfasına girer, gerekirse iframe içlerine de bakarak
    gizli .m3u8 sunucusunu bulur.
    """
    target_url = urljoin(current_domain, sample_channel['href'])
    print(f"[*] ADIM 3: Yayın sunucusu derinlemesine aranıyor ({target_url})...")
    
    try:
        session = requests.Session()
        res = session.get(target_url, headers=HEADERS, timeout=10)
        
        # 1. Deneme: Direkt kaynak kodunda .sbs linki var mı?
        server = extract_sbs_link(res.text)
        if server: return server
        
        # 2. Deneme: Sayfadaki 'iframe'lerin içine girip bak
        soup = BeautifulSoup(res.text, 'html.parser')
        iframes = soup.find_all('iframe')
        
        for iframe in iframes:
            src = iframe.get('src')
            if src and "http" in src:
                # Iframe linki relative (göreli) ise tam yap
                if not src.startswith("http"):
                    src = urljoin(current_domain, src)
                
                print(f"   > Iframe taranıyor: {src}")
                try:
                    iframe_res = session.get(src, headers=HEADERS, timeout=5)
                    server = extract_sbs_link(iframe_res.text)
                    if server:
                        print(f"[+] Iframe içinde bulundu!")
                        return server
                except: continue

        # Bulunamazsa varsayılan
        print("[!] Otomatik bulunamadı, varsayılan sunucu kullanılıyor.")
        return "https://56r.d72577a9dd0ec17.sbs/"

    except Exception as e:
        print(f"[!] Hata: {e}")
        return "https://56r.d72577a9dd0ec17.sbs/"

def extract_sbs_link(text):
    """Metin içinden .sbs veya .m3u8 linkini ayıklar."""
    # .sbs uzantılı link öncelikli
    match = re.search(r'(https?://[^\s"\'<>]+\.sbs/)', text)
    if match:
        server = match.group(1)
        print(f"[+] SUNUCU BULUNDU: {server}")
        return server
        
    # Genel .m3u8 linki
    match_gen = re.search(r'(https?://[^\s"\'<>]+\.m3u8)', text)
    if match_gen:
        full = match_gen.group(1)
        base = full.rsplit('/', 1)[0] + '/'
        print(f"[+] SUNUCU BULUNDU (Genel): {base}")
        return base
    return None

def save_outputs(channels, stream_base_url, current_domain):
    final_data = []
    seen_ids = set() # Tekrarı önlemek için

    for c in channels:
        if c['id'] in seen_ids: continue
        
        c["final_url"] = f"{stream_base_url}{c['id']}.m3u8"
        c["referer"] = current_domain
        final_data.append(c)
        seen_ids.add(c['id'])
        
    # JSON
    with open("trgoals.json", "w", encoding="utf-8") as f:
        json.dump(final_data, f, ensure_ascii=False, indent=4)

    # M3U
    with open("trgoals.m3u", "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        f.write(f'#EXTVLCOPT:http-referrer={current_domain}\n')
        
        for c in final_data:
            f.write(f'#EXTINF:-1 group-title="{c["category"]}",{c["name"]}\n')
            f.write(f'#EXTVLCOPT:http-referrer={current_domain}\n')
            f.write(f'{c["final_url"]}\n')
            
    print(f"\n[*] İŞLEM TAMAM: {len(final_data)} kanal güncel domain ile kaydedildi.")

def main():
    # 1. Otomatik Domain Bul
    current_domain, html_content = find_active_domain()
    if not current_domain: return
    
    # 2. Kanal Listesini Çek
    channels = step2_parse_channels(html_content, current_domain)
    if not channels: return
    
    # 3. Yayın Sunucusunu Bul (Iframe taramalı)
    # Genelde ilk maç aktiftir
    sample = channels[0]
    stream_base_url = step3_find_stream_server_recursive(current_domain, sample)
    
    # 4. Kaydet
    save_outputs(channels, stream_base_url, current_domain)

if __name__ == "__main__":
    main()
