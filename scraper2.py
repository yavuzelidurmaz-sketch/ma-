import re
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# Başlangıç Adresi (Yönlendirmeleri takip eder)
ENTRY_URL = "https://trgoalsgiris.xyz/" 
# Alternatif olarak senin attığın t.co linkini de buraya yazabilirsin, script onu da çözer.

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
}

def step1_get_site_content():
    """1. ADIM: Siteye girer, yönlendirmeleri izler ve HTML'i alır."""
    print(f"[*] ADIM 1: Siteye bağlanılıyor ({ENTRY_URL})...")
    try:
        session = requests.Session()
        # allow_redirects=True sayesinde t.co gibi linkleri otomatik takip eder
        response = session.get(ENTRY_URL, headers=HEADERS, timeout=20, allow_redirects=True)
        response.encoding = 'utf-8'
        
        final_url = response.url.rstrip('/')
        print(f"[+] Güncel Site Adresi: {final_url}")
        
        return final_url, response.text
    except Exception as e:
        print(f"[!] Siteye erişim hatası: {e}")
        return None, None

def step2_parse_channels(html_content, base_url):
    """2. ADIM: HTML'i analiz edip maçları ve kanalları listeler."""
    print("[*] ADIM 2: Maçlar ve kanallar ayrıştırılıyor...")
    
    soup = BeautifulSoup(html_content, 'html.parser')
    channels = []
    
    # Senin attığın HTML yapısı: <a class="channel-item" ...>
    # Hem maçları hem 7/24 kanalları bulur
    items = soup.find_all('a', class_='channel-item')
    
    for item in items:
        try:
            # 1. ID'yi al (href içinden)
            href = item.get('href')
            if 'id=' in href:
                stream_id = href.split('id=')[1]
            else:
                continue

            # 2. Kategoriyi al
            cat_raw = item.get('data-category', 'other')
            category = "Genel"
            if cat_raw == 'football': category = "Futbol"
            elif cat_raw == 'basketball': category = "Basketbol"
            elif cat_raw == '24-7': category = "7/24 TV"
            
            # 3. İsmi al (İkonu temizle, sadece metni al)
            name_div = item.find('div', class_='channel-name')
            if name_div:
                channel_name = name_div.get_text(strip=True)
            else:
                channel_name = f"Kanal {stream_id}"

            # 4. Logo (Site genelinde özel logo yok, kategoriye göre ikon verebiliriz)
            # Şimdilik boş geçiyoruz, m3u'da site iconu kullanılacak.

            channels.append({
                "id": stream_id,
                "name": channel_name,
                "category": category,
                "href": href
            })
            
        except Exception:
            continue
            
    print(f"[+] Toplam {len(channels)} adet içerik bulundu.")
    return channels

def step3_find_stream_server(current_domain, sample_channel):
    """3. ADIM: Bir kanala girip .sbs veya .m3u8 sunucusunu bulur."""
    
    # Örn: https://trgoals.xyz/channel.html?id=yayin1
    # urljoin kullanarak hatasız birleştirme yapıyoruz
    target_url = urljoin(current_domain, sample_channel['href'])
    
    print(f"[*] ADIM 3: Yayın sunucusu aranıyor ({target_url})...")
    
    try:
        res = requests.get(target_url, headers=HEADERS, timeout=15)
        
        # 1. Öncelik: .sbs uzantılı sunucu (Senin örneğin)
        # Regex: https://...../yayin1.m3u8 bulur
        match = re.search(r'(https?://[^\s"\'<>]+\.sbs/)', res.text)
        
        if match:
            server = match.group(1)
            print(f"[+] SUNUCU BULUNDU (.sbs): {server}")
            return server

        # 2. Öncelik: Herhangi bir .m3u8 linki
        match_gen = re.search(r'(https?://[^\s"\'<>]+\.m3u8)', res.text)
        if match_gen:
            full_link = match_gen.group(1)
            # Linkin sonundaki dosya adını at, geriye sunucu kalsın
            base_url = full_link.rsplit('/', 1)[0] + '/'
            print(f"[+] SUNUCU BULUNDU (Genel): {base_url}")
            return base_url

        print("[!] Otomatik sunucu bulunamadı. Varsayılan deneniyor.")
        return "https://56r.d72577a9dd0ec17.sbs/" # Senin verdiğin örnek sunucu (Fallback)

    except Exception as e:
        print(f"[!] Hata: {e}")
        return "https://56r.d72577a9dd0ec17.sbs/"

def save_outputs(channels, stream_base_url, current_domain):
    """Dosyaları oluşturur."""
    
    final_data = []
    for c in channels:
        # Final URL: Sunucu + ID + .m3u8
        c["final_url"] = f"{stream_base_url}{c['id']}.m3u8"
        c["referer"] = current_domain
        final_data.append(c)
        
    # 1. JSON
    with open("trgoals.json", "w", encoding="utf-8") as f:
        json.dump(final_data, f, ensure_ascii=False, indent=4)

    # 2. M3U
    with open("trgoals.m3u", "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        f.write(f'#EXTVLCOPT:http-referrer={current_domain}\n')
        
        for c in final_data:
            # Grup başlığı ve isim
            f.write(f'#EXTINF:-1 group-title="{c["category"]}",{c["name"]}\n')
            f.write(f'#EXTVLCOPT:http-referrer={current_domain}\n')
            f.write(f'{c["final_url"]}\n')
            
    print(f"\n[*] İşlem Tamamlandı! {len(final_data)} kanal dosyaya yazıldı.")

def main():
    # 1. Siteyi Bul
    current_domain, html_content = step1_get_site_content()
    if not current_domain: return
    
    # 2. Kanalları Ayrıştır (BeautifulSoup ile)
    channels = step2_parse_channels(html_content, current_domain)
    if not channels:
        print("[!] Hiç kanal bulunamadı.")
        return
        
    # 3. Sunucuyu Bul (Listedeki ilk yayını kullanarak)
    # Genelde ilk yayın aktiftir (yayin1)
    sample_channel = channels[0]
    stream_base_url = step3_find_stream_server(current_domain, sample_channel)
    
    # 4. Kaydet
    save_outputs(channels, stream_base_url, current_domain)

if __name__ == "__main__":
    main()
