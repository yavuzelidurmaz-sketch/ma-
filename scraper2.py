import re
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# Başlangıç numarası (Otomatik bulma için)
LAST_KNOWN_NUMBER = 1514
DOMAIN_EXTENSION = ".xyz"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Referer": "https://www.google.com/"
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
    print("[!] Hiçbir domain çalışmıyor. Manuel kontrol gerekebilir.")
    return None, None

def extract_channel_info(item, default_category="Genel"):
    """Tek bir linkten veri ayıklar (Kategori tespiti geliştirildi)."""
    try:
        href = item.get('href')
        if not href or 'id=' not in href: return None
        
        stream_id = href.split('id=')[1]
        
        # 1. Kategori Tespiti (Önce data-category'ye bak, yoksa ikona bak)
        cat_raw = item.get('data-category', '')
        
        # İkon kontrolü (HTML içindeki <i class="...">)
        icon_class = ""
        icon_tag = item.find('i')
        if icon_tag and icon_tag.get('class'):
            icon_class = " ".join(icon_tag.get('class'))
            
        category = default_category
        
        # Detaylı Kategori Mantığı
        if 'football' in cat_raw or 'futbol' in icon_class:
            category = "Futbol"
        elif 'basketball' in cat_raw or 'basketball' in icon_class:
            category = "Basketbol"
        elif '24-7' in cat_raw:
            category = "7/24 TV"
        elif default_category != "Genel":
            category = default_category # Tab'dan gelen zorunlu kategori
            
        # İsim Tespiti
        name_div = item.find('div', class_='channel-name')
        if name_div:
            # İkon metnini temizle, sadece yazıyı al
            channel_name = name_div.get_text(strip=True)
        else:
            channel_name = f"Kanal {stream_id}"

        return {
            "id": stream_id,
            "name": channel_name,
            "category": category,
            "href": href
        }
    except: return None

def step2_parse_channels_advanced(html_content, base_url):
    """HTML'i Tablo Tablo (Div Div) tarar."""
    print("[*] ADIM 2: Kategori bazlı tarama yapılıyor...")
    
    soup = BeautifulSoup(html_content, 'html.parser')
    all_channels = []
    seen_ids = set() # Tekrarı önlemek için
    
    # -------------------------------------------------------
    # 1. MAÇLAR SEKMESİNİ TARA (Futbol & Basketbol Burada)
    # -------------------------------------------------------
    matches_tab = soup.find('div', id='matches-tab')
    if matches_tab:
        print("   > 'Canlı Maçlar' sekmesi taraniyor...")
        items = matches_tab.find_all('a', class_='channel-item')
        for item in items:
            # Burada kategori otomatik algılanacak (Futbol/Basketbol)
            ch = extract_channel_info(item, default_category="Genel")
            if ch and ch['id'] not in seen_ids:
                all_channels.append(ch)
                seen_ids.add(ch['id'])
    else:
        print("   ! 'matches-tab' bulunamadı.")

    # -------------------------------------------------------
    # 2. 7/24 KANALLAR SEKMESİNİ TARA (BeIN, S Sport Burada)
    # -------------------------------------------------------
    tv_tab = soup.find('div', id='24-7-tab')
    if tv_tab:
        print("   > '7/24 Kanallar' sekmesi taraniyor...")
        items = tv_tab.find_all('a', class_='channel-item')
        for item in items:
            # Buradaki her şeyi zorla "7/24 TV" yap
            ch = extract_channel_info(item, default_category="7/24 TV")
            if ch and ch['id'] not in seen_ids:
                all_channels.append(ch)
                seen_ids.add(ch['id'])
    else:
        # Belki ID değişmiştir, class ile geniş arama yapalım
        print("   ! '24-7-tab' bulunamadı, genel tarama yapılıyor...")
        # Bu durumda sayfadaki TÜM linkleri tarayıp eksikleri ekleyelim
        all_items = soup.find_all('a', class_='channel-item')
        for item in all_items:
            ch = extract_channel_info(item)
            if ch and ch['id'] not in seen_ids:
                # Eğer daha önce eklenmediyse ve kategori Genel kaldıysa 7/24 yapalım
                if ch['category'] == "Genel": ch['category'] = "7/24 TV"
                all_channels.append(ch)
                seen_ids.add(ch['id'])

    print(f"[+] Toplam {len(all_channels)} içerik (Futbol, Basketbol, TV) bulundu.")
    return all_channels

def step3_find_stream_server(current_domain, sample_channel):
    """Yayın sunucusunu bulur."""
    if not sample_channel: return "https://56r.d72577a9dd0ec17.sbs/"
    
    target_url = urljoin(current_domain, sample_channel['href'])
    print(f"[*] ADIM 3: Sunucu aranıyor ({target_url})...")
    
    try:
        res = requests.get(target_url, headers=HEADERS, timeout=10)
        
        # .sbs linki
        match = re.search(r'(https?://[^\s"\'<>]+\.sbs/)', res.text)
        if match: return match.group(1)
            
        # Genel .m3u8 linki
        match_gen = re.search(r'(https?://[^\s"\'<>]+\.m3u8)', res.text)
        if match_gen:
            full = match_gen.group(1)
            return full.rsplit('/', 1)[0] + '/'
            
        return "https://56r.d72577a9dd0ec17.sbs/"
    except:
        return "https://56r.d72577a9dd0ec17.sbs/"

def save_outputs(channels, stream_base_url, current_domain):
    final_data = []
    
    # Kategorileri sıralayalım: Önce Futbol, Sonra Basketbol, Sonra TV
    cat_order = {"Futbol": 1, "Basketbol": 2, "7/24 TV": 3, "Genel": 4}
    channels.sort(key=lambda x: cat_order.get(x['category'], 5))
    
    for c in channels:
        c["final_url"] = f"{stream_base_url}{c['id']}.m3u8"
        c["referer"] = current_domain
        final_data.append(c)
        
    with open("trgoals.json", "w", encoding="utf-8") as f:
        json.dump(final_data, f, ensure_ascii=False, indent=4)

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
    
    # Gelişmiş tarama fonksiyonunu çağırıyoruz
    channels = step2_parse_channels_advanced(html_content, current_domain)
    
    if not channels:
        print("[!] Kanal listesi boş kaldı.")
        return
    
    # Sunucuyu bul
    sample = channels[0]
    stream_base_url = step3_find_stream_server(current_domain, sample)
    
    save_outputs(channels, stream_base_url, current_domain)

if __name__ == "__main__":
    main()
