import json
import requests
import time

def web_search(query, topk=10, search_engine="google", mkt="zh-CN"):

    max_attempt = 3
    attempt = 0

    if search_engine == "google":

        search_engine_id = "b012454b0648148f0"
        api_key = "AIzaSyAcE_uJ2MjMcMKS5_zBQE8tYwr_RB-ss0k"
        google_url = f"https://www.googleapis.com/customsearch/v1?key={api_key}&q={query}&cx={search_engine_id}&num={topk}" 
        proxies = {
            "http": "http://127.0.0.1:7895",   
            "https": "http://127.0.0.1:7895",  
            "socks5": "socks5://127.0.0.1:7895"  
        }


        while attempt < max_attempt:
            try:
                response = requests.get(google_url, proxies=proxies)
                response.raise_for_status()

                data = response.json()
                if "items" in data:
                    # extract links
                    return data
                    # return [result['link'] for result in data["items"]]
                elif "spelling" in data:
                    new_query = data["spelling"]["correctedQuery"]
                    return web_search(new_query, topk)
                else:
                    # no result
                    print(f"【No_web_result】 {query}")
                    return []
            except Exception as e:
                print(f"【google_search_Error】 {e}")
                time.sleep(3)
                attempt += 1
        if attempt >= max_attempt:
            print("----------------google_search_retry_Error----------------")
            return []


    elif search_engine == "bing":
        subscriptionKey = "430135bcd8944d66a22f3e92d5a5d0d7"
        customConfigId = "cee1da4f-268c-4df0-a4ed-efd4b7d107ce"

        bing_url = f'https://api.bing.microsoft.com/v7.0/custom/search?q={query}&customconfig={customConfigId}&mkt={mkt}'
        print("mkt:",mkt)
        proxies = {
            "http": "http://127.0.0.1:7895",   
            "https": "http://127.0.0.1:7895",  
            "socks5": "socks5://127.0.0.1:7895"  
        }

        while attempt < max_attempt:
            try:
                response = requests.get(bing_url, headers={'Ocp-Apim-Subscription-Key': subscriptionKey}, proxies=proxies)
                response.raise_for_status()

                data = response.json()
                if "webPages" in data:
                    # extract links

                    file_name = f"{search_engine}.json"

                    with open(file_name, "w",encoding="utf-8") as json_file:
                        json.dump(data,json_file,ensure_ascii=False, indent=4)
                    return data
                    # return [result["url"]  for result in data["webPages"]["value"]]
                # elif "spelling" in data:
                #     new_query = data["spelling"]["correctedQuery"]
                #     return web_search(new_query, topk)
                else:
                    # no result
                    print(f"【No_web_result】 {query}")
                    return []
            except Exception as e:
                print(f"【bing_search_Error】 {e}")
                time.sleep(3)
                attempt += 1
        if attempt >= max_attempt:
            print("----------------google_search_retry_Error----------------")
            return []


if __name__ == "__main__":

    query ="什么是策略梯度"
    topk = 10
    search_engine = "bing"
    mkt = "zh-CN"
    content = web_search(query=query,topk=topk,search_engine=search_engine,mkt=mkt)

    # file_name = f"{search_engine}.json"

    # with open(file_name, "w",encoding="utf-8") as json_file:
    #     json.dump(content,json_file,ensure_ascii=False, indent=4)

    print(content)
    

