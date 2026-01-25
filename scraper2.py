import re
import json
import requests
import html

# Giriş Adresi (Yönlendirmeyi takip edeceğiz)
ENTRY_URL = "https://trgoalsgiris.xyz/"

# Tarayıcı Headerları
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Referer": "https://www.google.com/"
}

def step1_find_current_domain():
    """1. ADIM: Güncel site adresini bulur."""
    try:
        print(f"[*] ADIM 1: Güncel TRGoals adresi aranıyor...")
        session = requests.Session()
        response = session.get(ENTRY_URL, headers=HEADERS, timeout=15, allow_redirects=True)
        
        current_url = response.url
        if current_url.endswith('/'):
            current_url = current_url[:-1]
            
        print(f"[+] Güncel site bulundu: {current_url}")
        return current_url, response.text
    except Exception as e:
        print(f"[!] Hata (Site Bulunamadı): {e}")
        return None, None

def step2_scrape_channels_from_html(html_content):
    """2. ADIM: Sayfadaki maçları ve kanalları (isim, kategori, id) regex ile okur."""
    print("[*] ADIM 2: Sayfadaki maçlar taranıyor...")
    
    channels = []
    
    # HTML yapısına uygun Regex (Senin attığın koda göre ayarlandı)
    # <a href="/channel.html?id=yayin1" class="channel-item" data-category="football">
    # <div class="channel-name"><i class="..."></i> Maç Adı</div>
    
    pattern = r'<a href="/channel\.html\?id=([^"]+)" class="channel-item" data-category="([^"]+)">.*?<div class="channel-name">(?:<i class="[^"]+"></i>)?\s*(.*?)</div>'
    
    matches = re.finditer(pattern, html_content, re.DOTALL)
    
    for match in matches:
        stream_id = match.group(1)      # yayin1, yayinb5 vb.
        category_raw = match.group(2)   # football, basketball
        name_raw = match.group(3)       # Fenerbahçe - Göztepe
        
        # Kategoriyi güzelleştir
        category = "Genel"
        if "football" in category_raw: category = "Futbol"
        elif "basketball" in category_raw: category = "Basketbol"
        elif "24-7" in category_raw: category = "7/24 TV"
        
        # İsmi temizle (HTML entity'leri çöz)
        name = html.unescape(name_raw).strip()
        
        channels.append({
            "id": stream_id,
            "name": name,
            "category": category
        })
        
    print(f"[+] Toplam {len(channels)} adet maç/kanal bulundu.")
    return channels

def step3_find_stream_server(current_domain, sample_id="yayin1"):
    """3. ADIM: Bir kanal sayfasına girip gizli .m3u8 sunucusunu bulur."""
    
    # Örnek: https://trgoals88.com/channel.html?id=yayin1
    target_url = f"{current_domain}/channel.html?id={sample_id}"
    
    print(f"[*] ADIM 3: Yayın sunucusu aranıyor ({target_url})...")
    
    try:
        res = requests.get(target_url, headers=HEADERS, timeout=10)
        
        # Regex: https://...../yayin1.m3u8 yapısını arar.
        # Senin örneğin: https://56r.d72577a9dd0ec17.sbs/yayin1.m3u8
        
        match = re.search(r'(https?://[^\s"\'<>]+\.sbs/)', res.text)
        
        # Eğer .sbs değilse genel m3u8 arayalım
        if not match:
             match = re.search(r'(https?://[^\s"\'<>]+\.m3u8)', res.text)
             if match:
                 # Full linki bulduk, base'i ayıralım
                 full_link = match.group(1)
                 # Linkin sonundaki ID.m3u8 kısmını atıp base'i alıyoruz
                 base_url = full_link.rsplit('/', 1)[0] + '/'
                 print(f"[+] Yayın Sunucusu Bulundu (Genel): {base_url}")
                 return base_url

        if match:
            server_url = match.group(1)
            print(f"[+] Yayın Sunucusu Bulundu (.sbs): {server_url}")
            return server_url
        else:
            print("[!] Yayın sunucusu regex ile bulunamadı. Sayfa yapısı değişmiş olabilir.")
            # Debug: print(res.text[:500])
            return None
            
    except Exception as e:
        print(f"[!] Hata (Sunucu Bulma): {e}")
        return None

def save_files(channels, stream_base_url, current_domain):
    """Dosyaları oluşturur."""
    
    if not channels or not stream_base_url:
        print("[!] Veri eksik, dosya oluşturulmuyor.")
        return

    # 1. JSON Dosyası
    json_data = []
    for c in channels:
        final_url = f"{stream_base_url}{c['id']}.m3u8"
        c["final_url"] = final_url
        c["referer"] = current_domain
        json_data.append(c)
        
    with open("trgoals.json", "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=4)

    # 2. M3U Dosyası
    with open("trgoals.m3u", "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        f.write(f'#EXTVLCOPT:http-referrer={current_domain}\n')
        f.write(f'#EXTVLCOPT:http-user-agent={HEADERS["User-Agent"]}\n')
        
        for c in json_data:
            # Logo işlemleri (Basitçe site logosunu kullanabiliriz veya boş bırakabiliriz)
            # TRGoals HTML'inde logo url yok, o yüzden standart bir icon atayabilirsin
            
            f.write(f'#EXTINF:-1 group-title="{c["category"]}",{c["name"]}\n')
            f.write(f'#EXTVLCOPT:http-referrer={current_domain}\n')
            f.write(f'{c["final_url"]}\n')
            
    print(f"\n[*] Başarılı! trgoals.json ve trgoals.m3u oluşturuldu.")

def main():
    # 1. Siteyi Bul
    current_domain, html_content = step1_find_current_domain()
    if not current_domain: return
    
    # 2. Kanalları Listele (HTML'den oku)
    channels = step2_scrape_channels_from_html(html_content)
    if not channels:
        print("[!] Sitede hiç kanal bulunamadı veya yapı değişti.")
        return
        
    # 3. Yayın Sunucusunu Bul (Listedeki ilk kanalı kullanarak)
    # Genelde ilk kanal aktiftir, onu test için kullanıyoruz.
    sample_id = channels[0]['id']
    stream_base_url = step3_find_stream_server(current_domain, sample_id)
    
    if not stream_base_url:
        print("[!] Kritik: Yayın sunucusu bulunamadı.")
        return
        
    # 4. Kaydet
    save_files(channels, stream_base_url, current_domain)

if __name__ == "__main__":
    main()
