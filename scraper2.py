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

# Kategori Çeviri Sözlüğü
CAT_MAP = {
    "football": "Futbol",
    "basketball": "Basketbol",
    "volleyball": "Voleybol",
    "tennis": "Tenis",
    "24-7": "7/24 TV",
    "multi-screen": "Çoklu Ekran",
    "other": "Diğer"
}

def find_active_domain():
    """Çalışan siteyi bulur."""
    print("[*] ADIM 1: Güncel site taranıyor...")
    for i in range(0, 20):
        current_num = LAST_KNOWN_NUMBER + i
        candidate_url = f"https://trgoals{current_num}{DOMAIN_EXTENSION}/"
        try:
            res = requests.get(candidate_url, headers=HEADERS, timeout=5)
            if res.status_code == 200 and ("TRGoals" in res.text or "Canlı Maç" in res.text):
                print(f"[+] AKTİF SİTE: {candidate_url}")
                return candidate_url, res.text
        except: continue
    return None, None

def step2_parse_by_data_category(html_content):
    """
    HTML içindeki elementlere bakmaz.
    Direkt olarak 'data-category' özelliğine sahip olan HER ŞEYİ toplar.
    """
    print("[*] ADIM 2: 'data-category' taraması yapılıyor...")
    
    soup = BeautifulSoup(html_content, 'html.parser')
    all_channels = []
    seen_ids = set()
    
    # EN ÖNEMLİ KISIM: Sadece data-category özelliği olanları bul
    # Etiketin <a> veya <div> olması fark etmez.
    items = soup.find_all(attrs={"data-category": True})
    
    for item in items:
        try:
            # 1. Linki (href) var mı?
            href = item.get('href')
            if not href or 'id=' not in href: 
                continue # Linki yoksa geç
            
            stream_id = href.split('id=')[1]
            
            # Tekrar kontrolü
            if stream_id in seen_ids: 
                continue

            # 2. Kategoriyi Al
            raw_cat = item.get('data-category').lower()
            
            # Eğer filtre butonlarından biriyse (Tümü, Futbol butonu vb.) bunu atla
            # Sadece kanal linklerini almamız lazım. Linklerde 'channel.html' olur.
            if 'channel.html' not in href:
                continue

            # Kategoriyi Türkçeye çevir
            category = CAT_MAP.get(raw_cat, "Genel")
            
            # 3. İsmi Al
            # Genelde isim 'channel-name' class'lı div içindedir
            name_div = item.find('div', class_='channel-name')
            if name_div:
                name = name_div.get_text(strip=True)
            else:
                # Eğer div yoksa direkt metni almayı dene
                name = item.get_text(strip=True)
                if not name: name = f"Kanal {stream_id}"

            all_channels.append({
                "id": stream_id,
                "name": name,
                "category": category,
                "href": href
            })
            seen_ids.add(stream_id)
            
        except Exception: 
            continue

    print(f"[+] Toplam {len(all_channels)} içerik bulundu.")
    
    # Kategorilere göre sayıları yazdır (Kontrol için)
    cat_counts = {}
    for c in all_channels:
        cat = c['category']
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
    print(f"   > Detay: {cat_counts}")
    
    return all_channels

def step3_find_stream_server(current_domain, sample_channel):
    """Sunucuyu bulur."""
    if not sample_channel: return "https://56r.d72577a9dd0ec17.sbs/"
    target_url = urljoin(current_domain, sample_channel['href'])
    print(f"[*] ADIM 3: Sunucu aranıyor ({target_url})...")
    try:
        res = requests.get(target_url, headers=HEADERS, timeout=10)
        match = re.search(r'(https?://[^\s"\'<>]+\.sbs/)', res.text)
        if match: return match.group(1)
        match_gen = re.search(r'(https?://[^\s"\'<>]+\.m3u8)', res.text)
        if match_gen: return match_gen.group(1).rsplit('/', 1)[0] + '/'
    except: pass
    return "https://56r.d72577a9dd0ec17.sbs/"

def save_outputs(channels, stream_base_url, current_domain):
    final_data = []
    # Sıralama: Futbol -> Basket -> TV -> Diğer
    prio = {"Futbol": 1, "Basketbol": 2, "Voleybol": 3, "7/24 TV": 4, "Genel": 99}
    channels.sort(key=lambda x: prio.get(x['category'], 50))
    
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
    
    # Data-Category ile tara
    channels = step2_parse_by_data_category(html_content)
    
    if not channels:
        print("[!] Liste boş.")
        return
        
    sample = channels[0]
    stream_base_url = step3_find_stream_server(current_domain, sample)
    
    save_outputs(channels, stream_base_url, current_domain)

if __name__ == "__main__":
    main()
