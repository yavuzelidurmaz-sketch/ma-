import re

import json

import requests

from bs4 import BeautifulSoup

from urllib.parse import urljoin



# DİREKT ANA SAYFA ADRESİ (Bunu güncelledik)

ENTRY_URL = "https://trgoals1514.xyz/"



HEADERS = {

    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",

    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",

    "Referer": "https://www.google.com/"

}



def step1_get_site_content():

    """1. ADIM: Siteye girer ve HTML'i alır."""

    print(f"[*] ADIM 1: Siteye bağlanılıyor ({ENTRY_URL})...")

    try:

        session = requests.Session()

        # verify=False, SSL hatası verirse diye eklendi (bazen bu sitelerin sertifikası bozuk olabilir)

        response = session.get(ENTRY_URL, headers=HEADERS, timeout=20, allow_redirects=True)

        response.encoding = 'utf-8'

        

        # Eğer site bizi başka bir yere attıysa o adresi alalım

        final_url = response.url.rstrip('/')

        print(f"[+] Bağlanılan Adres: {final_url}")

        

        return final_url, response.text

    except Exception as e:

        print(f"[!] Siteye erişim hatası: {e}")

        return None, None



def step2_parse_channels(html_content, base_url):

    """2. ADIM: HTML'i analiz edip maçları ve kanalları listeler."""

    print("[*] ADIM 2: Kanal listesi taranıyor...")

    

    soup = BeautifulSoup(html_content, 'html.parser')

    channels = []

    

    # <a class="channel-item"> etiketlerini bul

    items = soup.find_all('a', class_='channel-item')

    

    for item in items:

        try:

            # 1. ID'yi al

            href = item.get('href')

            if not href or 'id=' not in href:

                continue

                

            stream_id = href.split('id=')[1]



            # 2. Kategoriyi al

            cat_raw = item.get('data-category', 'other')

            category = "Genel"

            if cat_raw == 'football': category = "Futbol"

            elif cat_raw == 'basketball': category = "Basketbol"

            elif cat_raw == '24-7': category = "7/24 TV"

            

            # 3. İsmi al

            # div class="channel-name" içindeki metni alıyoruz

            name_div = item.find('div', class_='channel-name')

            if name_div:

                channel_name = name_div.get_text(strip=True)

            else:

                channel_name = f"Kanal {stream_id}"



            channels.append({

                "id": stream_id,

                "name": channel_name,

                "category": category,

                "href": href

            })

            

        except Exception:

            continue

            

    if not channels:

        print("[!] Hata: Kanal bulunamadı. Gelen sayfanın başı şöyledir:")

        # Hata ayıklama için sayfanın ilk 500 karakterini ekrana basar

        print(html_content[:500])

    else:

        print(f"[+] Toplam {len(channels)} adet maç/kanal bulundu.")

        

    return channels



def step3_find_stream_server(current_domain, sample_channel):

    """3. ADIM: Bir kanala girip .sbs sunucusunu bulur."""

    

    # Linkleri birleştir (örn: https://trgoals1514.xyz + /channel.html?id=yayin1)

    target_url = urljoin(current_domain, sample_channel['href'])

    

    print(f"[*] ADIM 3: Sunucu aranıyor ({target_url})...")

    

    try:

        res = requests.get(target_url, headers=HEADERS, timeout=15)

        

        # 1. Öncelik: .sbs uzantılı link

        match = re.search(r'(https?://[^\s"\'<>]+\.sbs/)', res.text)

        if match:

            server = match.group(1)

            print(f"[+] SUNUCU BULUNDU (.sbs): {server}")

            return server



        # 2. Öncelik: Herhangi bir .m3u8 linki

        match_gen = re.search(r'(https?://[^\s"\'<>]+\.m3u8)', res.text)

        if match_gen:

            full_link = match_gen.group(1)

            base_url = full_link.rsplit('/', 1)[0] + '/'

            print(f"[+] SUNUCU BULUNDU (Genel): {base_url}")

            return base_url



        print("[!] Sunucu bulunamadı. Varsayılan (yedek) kullanılıyor.")

        return "https://56r.d72577a9dd0ec17.sbs/" # Yedek sunucu



    except Exception as e:

        print(f"[!] Hata: {e}")

        return "https://56r.d72577a9dd0ec17.sbs/"



def save_outputs(channels, stream_base_url, current_domain):

    """Dosyaları kaydeder."""

    

    final_data = []

    for c in channels:

        # Final URL oluştur

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

            # Kategori ve isim

            f.write(f'#EXTINF:-1 group-title="{c["category"]}",{c["name"]}\n')

            f.write(f'#EXTVLCOPT:http-referrer={current_domain}\n')

            f.write(f'{c["final_url"]}\n')

            

    print(f"\n[*] İşlem Başarılı! trgoals.json ve trgoals.m3u kaydedildi.")



def main():

    # 1. Siteyi Bul

    current_domain, html_content = step1_get_site_content()

    if not current_domain: return

    

    # 2. Kanalları Ayrıştır

    channels = step2_parse_channels(html_content, current_domain)

    if not channels:

        return

        

    # 3. Sunucuyu Bul (İlk kanaldan)

    sample_channel = channels[0]

    stream_base_url = step3_find_stream_server(current_domain, sample_channel)

    

    # 4. Kaydet

    save_outputs(channels, stream_base_url, current_domain)



if __name__ == "__main__":

    main() 
