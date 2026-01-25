import re
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# Başlangıç Numarası
LAST_KNOWN_NUMBER = 1514
DOMAIN_EXTENSION = ".xyz"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Referer": "https://www.google.com/"
}

# ---------------------------------------------------------
# KATEGORİ SÖZLÜĞÜ (İngilizce -> Türkçe)
# ---------------------------------------------------------
CATEGORY_TRANSLATIONS = {
    "football": "Futbol",
    "basketball": "Basketbol",
    "volleyball": "Voleybol",
    "tennis": "Tenis",
    "handball": "Hentbol",
    "motor-sports": "Motor Sporları",
    "boxing": "Dövüş Sporları",
    "ufc": "Dövüş Sporları",
    "formula1": "Formula 1",
    "snooker": "Snooker",
    "other": "Diğer Sporlar",
    "24-7": "7/24 TV",
    "multi-screen": "Çoklu Ekran"
}

# İKON SÖZLÜĞÜ (Yedek Plan)
ICON_MAP = {
    "fa-futbol": "Futbol",
    "fa-basketball-ball": "Basketbol",
    "fa-volleyball-ball": "Voleybol",
    "fa-table-tennis": "Masa Tenisi",
    "fa-car": "Motor Sporları",
    "fa-flag-checkered": "Formula 1",
    "fa-tv": "7/24 TV"
}

def find_active_domain():
    """Çalışan site adresini bulur."""
    print("[*] ADIM 1: Güncel site adresi taranıyor...")
    for i in range(0, 20):
        current_num = LAST_KNOWN_NUMBER + i
        candidate_url = f"https://trgoals{current_num}{DOMAIN_EXTENSION}/"
        try:
            print(f"   > Deneniyor: {candidate_url}")
            res = requests.get(candidate_url, headers=HEADERS, timeout=5)
            if res.status_code == 200 and "TRGoals" in res.text:
                print(f"[+] AKTİF SİTE BULUNDU: {candidate_url}")
                return candidate_url, res.text
        except: continue
    print("[!] Hiçbir domain çalışmıyor.")
    return None, None

def determine_category(item):
    """
    Önce data-category'ye bakar, bulamazsa ikona bakar.
    Hiçbiri yoksa 'Diğer' der.
    """
    # 1. Yöntem: data-category özniteliği
    cat_raw = item.get('data-category', '').lower()
    
    if cat_raw in CATEGORY_TRANSLATIONS:
        return CATEGORY_TRANSLATIONS[cat_raw]
    
    # Eğer listede yoksa ama doluysa (örn: 'rugby'), baş harfini büyüt kullan
    if cat_raw and cat_raw != "other":
        return cat_raw.capitalize()

    # 2. Yöntem: İkon sınıfı (fa-volleyball-ball vb.)
    icon_tag = item.find('i')
    if icon_tag:
        classes = icon_tag.get('class', [])
        for cls in classes:
            if cls in ICON_MAP:
                return ICON_MAP[cls]
            # Genel tarama: 'volleyball' kelimesi geçiyor mu?
            if 'volleyball' in cls: return "Voleybol"
            if 'tennis' in cls: return "Tenis"
    
    return "Diğer Sporlar"

def step2_parse_all_channels(html_content):
    """HTML içindeki TÜM linkleri tarar ve kategorize eder."""
    print("[*] ADIM 2: Tüm spor dalları taranıyor...")
    
    soup = BeautifulSoup(html_content, 'html.parser')
    all_channels = []
    seen_ids = set()
    
    # Sayfadaki TÜM '.channel-item' sınıfına sahip linkleri bul
    # Artık sadece tab'lara bakmıyoruz, her yere bakıyoruz.
    items = soup.find_all('a', class_='channel-item')
    
    for item in items:
        try:
            href = item.get('href')
            if not href or 'id=' not in href: continue
            
            stream_id = href.split('id=')[1]
            if stream_id in seen_ids: continue # Tekrarı önle
            
            # Kategori Belirle (Voleybol, Basket, vb.)
            category = determine_category(item)
            
            # İsim Belirle
            name_div = item.find('div', class_='channel-name')
            if name_div:
                channel_name = name_div.get_text(strip=True)
            else:
                channel_name = f"Kanal {stream_id}"

            all_channels.append({
                "id": stream_id,
                "name": channel_name,
                "category": category,
                "href": href
            })
            seen_ids.add(stream_id)
            
        except Exception: continue

    print(f"[+] Toplam {len(all_channels)} içerik bulundu (Futbol, Voleybol, Tenis vb.).")
    return all_channels

def step3_find_stream_server(current_domain, sample_channel):
    """Yayın sunucusunu bulur."""
    if not sample_channel: return "https://56r.d72577a9dd0ec17.sbs/"
    
    target_url = urljoin(current_domain, sample_channel['href'])
    print(f"[*] ADIM 3: Sunucu aranıyor ({target_url})...")
    
    try:
        res = requests.get(target_url, headers=HEADERS, timeout=10)
        
        match = re.search(r'(https?://[^\s"\'<>]+\.sbs/)', res.text)
        if match: return match.group(1)
            
        match_gen = re.search(r'(https?://[^\s"\'<>]+\.m3u8)', res.text)
        if match_gen:
            full = match_gen.group(1)
            return full.rsplit('/', 1)[0] + '/'
            
        return "https://56r.d72577a9dd0ec17.sbs/"
    except:
        return "https://56r.d72577a9dd0ec17.sbs/"

def save_outputs(channels, stream_base_url, current_domain):
    final_data = []
    
    # Sıralama: Futbol > Basket > Voleybol > Tenis > TV > Diğer
    # Bu sıralama M3U listesinde en üstte neyin görüneceğini belirler
    priority = {
        "Futbol": 1, 
        "Basketbol": 2, 
        "Voleybol": 3, 
        "Tenis": 4, 
        "7/24 TV": 90, 
        "Diğer Sporlar": 99
    }
    
    channels.sort(key=lambda x: priority.get(x['category'], 50))
    
    for c in channels:
        c["final_url"] = f"{stream_base_url}{c['id']}.m3u8"
        c["referer"] = current_domain
        final_data.append(c)
        
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
            
    print(f"\n[*] İŞLEM TAMAM! {len(final_data)} kanal başarıyla kaydedildi.")

def main():
    current_domain, html_content = find_active_domain()
    if not current_domain: return
    
    # Tüm sporları tara
    channels = step2_parse_all_channels(html_content)
    
    if not channels:
        print("[!] Kanal listesi boş kaldı.")
        return
    
    # Sunucuyu bul
    sample = channels[0]
    stream_base_url = step3_find_stream_server(current_domain, sample)
    
    save_outputs(channels, stream_base_url, current_domain)

if __name__ == "__main__":
    main()
