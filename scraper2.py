import re
import json
import requests
import html

# Giriş Adresi
ENTRY_URL = "https://trgoalsgiris.xyz/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Referer": "https://www.google.com/"
}

def step1_find_current_domain():
    """1. ADIM: Güncel site adresini ve HTML içeriğini alır."""
    try:
        print(f"[*] ADIM 1: Siteye bağlanılıyor...")
        session = requests.Session()
        response = session.get(ENTRY_URL, headers=HEADERS, timeout=20, allow_redirects=True)
        response.encoding = 'utf-8' # Türkçe karakter sorunu olmasın
        
        current_url = response.url
        if current_url.endswith('/'):
            current_url = current_url[:-1]
            
        print(f"[+] Site URL: {current_url}")
        
        # Basit JS Yönlendirme Kontrolü (Eğer site boşsa ve yönlendirme varsa)
        if "window.location.replace" in response.text or "window.location.href" in response.text:
            redirect_match = re.search(r'window\.location\.(?:replace|href)\s*=\s*["\']([^"\']+)["\']', response.text)
            if redirect_match:
                new_url = redirect_match.group(1)
                print(f"[!] JS Yönlendirmesi tespit edildi: {new_url}")
                if not new_url.startswith("http"):
                    # Relative path ise domainle birleştir
                    new_url = current_url + "/" + new_url.lstrip("/")
                return step1_direct_url(new_url)

        return current_url, response.text
    except Exception as e:
        print(f"[!] Hata (Site Bulunamadı): {e}")
        return None, None

def step1_direct_url(url):
    """Yönlendirilen adrese gider."""
    try:
        res = requests.get(url, headers=HEADERS, timeout=20)
        res.encoding = 'utf-8'
        return url.rstrip('/'), res.text
    except:
        return None, None

def step2_scrape_channels_flexible(html_content):
    """2. ADIM: HTML içinden kanalları ESNEK yöntemle (sıraya bakmaksızın) çeker."""
    print("[*] ADIM 2: Kanal listesi taranıyor (Esnek Mod)...")
    
    channels = []
    
    # YÖNTEM: Önce class="channel-item" olan tüm <a> bloklarını bulalım.
    # Bu regex, <a> etiketinin tamamını ve kapanışına kadar olan içeriği alır.
    link_blocks = re.findall(r'(<a [^>]*class=["\']channel-item["\'][^>]*>.*?</a>)', html_content, re.DOTALL)
    
    for block in link_blocks:
        try:
            # 1. ID'yi bul (href içinden)
            # href="/channel.html?id=yayin1" veya href="channel.html?id=yayin1"
            id_match = re.search(r'id=([a-zA-Z0-9_-]+)', block)
            if not id_match: continue
            stream_id = id_match.group(1)

            # 2. Kategoriyi bul (data-category içinden)
            cat_match = re.search(r'data-category=["\']([^"\']+)["\']', block)
            category_raw = cat_match.group(1) if cat_match else "other"
            
            # Kategoriyi güzelleştir
            if "football" in category_raw: category = "Futbol"
            elif "basketball" in category_raw: category = "Basketbol"
            elif "24-7" in category_raw: category = "7/24 TV"
            else: category = "Diğer"

            # 3. Kanal İsmini bul (channel-name div'i içinden)
            name_match = re.search(r'class=["\']channel-name["\'][^>]*>(?:<i[^>]*></i>)?\s*(.*?)<', block, re.DOTALL)
            if name_match:
                name_raw = name_match.group(1)
                name = html.unescape(name_raw).strip() # HTML karakterlerini temizle (&amp; gibi)
            else:
                name = f"Kanal {stream_id}"

            channels.append({
                "id": stream_id,
                "name": name,
                "category": category
            })
            
        except Exception:
            continue
            
    if len(channels) == 0:
        print("[!] Hata: Kanal bulunamadı. HTML yapısı farklı olabilir.")
        # Debug: HTML'in bir kısmını yazdıralım ki sorunu görelim
        # print(html_content[:1000])
    else:
        print(f"[+] Toplam {len(channels)} kanal bulundu.")
        
    return channels

def step3_find_stream_server(current_domain, sample_id):
    """3. ADIM: Yayın sunucusunu bulur (.sbs veya genel .m3u8)."""
    
    # Örn: https://trgoals.xyz/channel.html?id=yayin1
    target_url = f"{current_domain}/channel.html?id={sample_id}"
    print(f"[*] ADIM 3: Sunucu aranıyor ({target_url})...")
    
    try:
        res = requests.get(target_url, headers=HEADERS, timeout=15)
        
        # 1. Öncelik: .sbs uzantılı sunucu (Senin verdiğin örnekteki gibi)
        match_sbs = re.search(r'(https?://[^\s"\'<>]+\.sbs/)', res.text)
        if match_sbs:
            server = match_sbs.group(1)
            print(f"[+] Sunucu Bulundu (.sbs): {server}")
            return server
            
        # 2. Öncelik: Genel .m3u8 linki bulup base url'i çıkarmak
        match_m3u8 = re.search(r'(https?://[^\s"\'<>]+\.m3u8)', res.text)
        if match_m3u8:
            full_link = match_m3u8.group(1)
            # Linkin sonundaki dosya ismini at, geriye sunucu kalsın
            # örn: https://server.com/live/yayin1.m3u8 -> https://server.com/live/
            base_url = full_link.rsplit('/', 1)[0] + '/'
            print(f"[+] Sunucu Bulundu (Genel): {base_url}")
            return base_url
            
        print("[!] Yayın sunucusu regex ile bulunamadı.")
        return None
            
    except Exception as e:
        print(f"[!] Sunucu bulma hatası: {e}")
        return None

def save_files(channels, stream_base_url, current_domain):
    """Dosyaları kaydeder."""
    if not channels or not stream_base_url: return

    # 1. JSON
    final_data = []
    for c in channels:
        # Final URL oluştur: Sunucu + ID + .m3u8
        c["final_url"] = f"{stream_base_url}{c['id']}.m3u8"
        c["referer"] = current_domain
        # Logoları sitenin kendisinden çekelim (varsa) veya genel bir ikon
        # TRGoals'da logo genelde yok ama kategoriye göre ikon atayabilirsin app tarafında
        final_data.append(c)
        
    with open("trgoals.json", "w", encoding="utf-8") as f:
        json.dump(final_data, f, ensure_ascii=False, indent=4)

    # 2. M3U
    with open("trgoals.m3u", "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        f.write(f'#EXTVLCOPT:http-referrer={current_domain}\n')
        f.write(f'#EXTVLCOPT:http-user-agent={HEADERS["User-Agent"]}\n')
        
        for c in final_data:
            f.write(f'#EXTINF:-1 group-title="{c["category"]}",{c["name"]}\n')
            f.write(f'#EXTVLCOPT:http-referrer={current_domain}\n')
            f.write(f'{c["final_url"]}\n')
            
    print(f"\n[*] İşlem Tamam! {len(final_data)} kanal kaydedildi.")

def main():
    # 1. Siteyi Bul
    current_domain, html_content = step1_find_current_domain()
    if not current_domain or not html_content:
        print("[!] Siteye erişilemedi.")
        return
    
    # 2. Kanalları Çek (Esnek Mod)
    channels = step2_scrape_channels_flexible(html_content)
    if not channels:
        return
        
    # 3. Sunucuyu Bul (İlk kanalı kullanarak)
    # Genelde ilk kanal yayındadır, test için onu kullanıyoruz
    sample_id = channels[0]['id']
    stream_base_url = step3_find_stream_server(current_domain, sample_id)
    
    # Eğer sunucu bulunamazsa manuel bir fallback (yedek) deneyebiliriz
    if not stream_base_url:
        print("[!] Sunucu bulunamadı, varsayılan deneniyor...")
        # Senin verdiğin örnekteki sunucuyu yedek olarak ekleyelim
        stream_base_url = "https://56r.d72577a9dd0ec17.sbs/"
        
    # 4. Kaydet
    save_files(channels, stream_base_url, current_domain)

if __name__ == "__main__":
    main()
