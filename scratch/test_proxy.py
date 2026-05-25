import requests
import random

def fetch_with_proxy(url):
    print(f"Fetching proxies from ProxyScrape...")
    try:
        r = requests.get('https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=3000&country=all&ssl=all&anonymity=all', timeout=10)
        proxies_list = r.text.strip().split('\r\n')
        proxies_list = [p.strip() for p in proxies_list if p.strip()]
        print(f"Loaded {len(proxies_list)} proxies.")
    except Exception as e:
        print(f"Failed to fetch proxy list: {e}")
        return None

    random.shuffle(proxies_list)

    # Try up to 30 proxies to find one that works
    for i, proxy_ip in enumerate(proxies_list[:30]):
        proxy_url = f"http://{proxy_ip}"
        proxies = {
            "http": proxy_url,
            "https": proxy_url
        }
        print(f"[{i+1}/30] Trying proxy: {proxy_ip}...")
        try:
            response = requests.get(url, proxies=proxies, timeout=5)
            if response.status_code == 200:
                text = response.text
                if "<!DOCTYPE html>" not in text and "Coljuegos" not in text:
                    print(f"SUCCESS with proxy {proxy_ip}! Length: {len(text)}")
                    print("Start of content:")
                    print(text[:300])
                    return response
                else:
                    print(f"Failed: Proxy returned Coljuegos block or HTML instead of CSV.")
            else:
                print(f"Failed: Status code {response.status_code}")
        except Exception as e:
            print(f"Failed: {e}")
            continue

    print("Could not fetch the URL with any proxy.")
    return None

if __name__ == "__main__":
    print("--- TESTING FIXTURES.CSV ---")
    fetch_with_proxy("http://www.football-data.co.uk/fixtures.csv")
    print("\n--- TESTING SEASON DATA (E0.csv) ---")
    fetch_with_proxy("http://www.football-data.co.uk/mmz4281/2526/E0.csv")
