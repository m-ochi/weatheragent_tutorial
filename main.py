# main.py
import os
import asyncio
from typing import Dict, Any
import yaml
import requests
from google.adk.agents import Agent
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types

with open("./config.yml", 'r') as file:
    config = yaml.safe_load(file)

# -------------------------
# 0) モデル設定（Gemini）
# -------------------------
os.environ["GOOGLE_API_KEY"] = config["gemini_api_key"]
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "False"
MODEL_GEMINI = "gemini-2.0-flash"

os.environ["WEATHERAPI_KEY"] = config["weather_api_key"]
os.environ["EXCHANGERATEAPI_KEY"] = config["exchangerate_api_key"]

# -------------------------
# 1) 複数ツール（モック実装）
# -------------------------
def get_weather(city: str) -> Dict[str, Any]:
    BASE_URL = "https://api.weatherapi.com/v1/current.json"
    API_KEY = os.environ["WEATHERAPI_KEY"]

    params = {"key": API_KEY, "q": city, "aqi": "no"}
    r = requests.get(BASE_URL, params=params, timeout=10)
    r.raise_for_status()          # 4xx/5xx を例外に
    data = r.json()
    # 使いやすい形で抜粋
    loc = data["location"]
    cur = data["current"]
    return {
        "name": loc["name"],
        "country": loc["country"],
        "localtime": loc["localtime"],
        "temp_c": cur["temp_c"],
        "condition": cur["condition"]["text"],
        "wind_kph": cur["wind_kph"],
        "humidity": cur["humidity"],
    }

def convert_currency(amount: float, from_currency: str, to_currency: str) -> Dict[str, Any]:
    """
    通貨を変換する関数
    from_currency, to_currencyは、JPY,USDのようにコードで入力する。
    """
    BASE_URL = " https://v6.exchangerate-api.com/v6/"
    API_KEY = os.environ["EXCHANGERATEAPI_KEY"]
    url = f"https://v6.exchangerate-api.com/v6/{API_KEY}/latest/{from_currency.upper()}"

    print(url)
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    data = r.json()
    if data.get("result") != "success":
        raise RuntimeError(f"API error: {data}")

    rate = data["conversion_rates"][to_currency]
    resDic = {
        "status": "success",
             }

    return {"status": "success", "converted": amount * rate, "rate": rate}

def suggest_outfit(temp_c: float) -> Dict[str, Any]:
    if temp_c < 10: rec = "コートと防寒具"
    elif temp_c < 18: rec = "薄めのジャケット"
    elif temp_c < 24: rec = "長袖シャツ"
    else: rec = "半袖・薄着"
    return {"status": "success", "suggestion": rec}

# -------------------------
# 2) Agent 定義
# -------------------------
TRAVEL_INSTRUCTION = """
あなたは旅行コンシェルジュAIです。ユーザーの意図に応じて、以下のツールを自律的に使い分けて回答してください。
利用可能ツール:
- get_weather(city: str)
- convert_currency(amount: float, from_currency: str, to_currency: str)
- suggest_outfit(temp_c: float)

【必須ルール】
1) 服装に関する相談（例：「何を着ればいい？」）が都市と結び付いている／暗に都市が想定される場合は、
   まず必ず get_weather(city) を呼び出して天気を取得する。ユーザーに天気を尋ねてはならない。
   都市名は表記ゆれを正規化して扱う（例：「東京」「とうきょう」→ "Tokyo"）。

2) 天気レポートから摂氏温度（例：18°C, 25℃ など）を抽出し、その数値を使って suggest_outfit(temp_c) を呼び出す。
   温度表記が見つからない場合は文面から最も妥当な気温を推定するか、どうしても不可能なら都市のみ確認する質問を1回だけ行う。

3) ユーザーが特定都市の天気を尋ねた場合は get_weather を、為替換算が含まれる場合は convert_currency を使う。
   1ターン内で複数ツールを連続利用してよい（例：天気→服装、為替→結果提示）。

4) ツールが error を返した場合は簡潔に理由を伝え、代替案（別都市の例、対応可能な都市の提示、再入力のお願い）を提案する。

5) 出力は簡潔・明瞭に。数値や単位（°C、通貨）を明示し、必要なら根拠（取得した天気要約や換算レート）を短く添える。

【Few-shot 例】
- 例1:
  User: 「東京に行くけど何を着ればいい？」
  Plan: get_weather("東京") → レポートから °C を抽出 → suggest_outfit(temp_c) → 結果を日本語で提示。

- 例2:
  User: 「ロンドンの天気と、1万円をポンドに替えるといくら？」
  Plan: get_weather("ロンドン") → convert_currency(10000, "JPY", "GBP") → 両方の結果をまとめて提示。

- 例3:
  User: 「大阪の服装を教えて」
  Plan: get_weather("大阪") → 未対応で error の場合は、対応都市の例を出しつつ、都市確認を1回だけ行う。
"""

#print(type(TRAVEL_INSTRUCTION))

agent = Agent(
    name="travel_concierge_v1",
    model=MODEL_GEMINI,
    description="Multi-tool demo: weather, currency, outfits.",
    instruction=TRAVEL_INSTRUCTION,
    tools=[get_weather, convert_currency, suggest_outfit],
)

# -------------------------
# 3) 会話実行ヘルパ
# -------------------------
async def ask(runner: Runner, user_id: str, session_id: str, text: str):
    print(f"\n>>> {text}")
    content = types.Content(role="user", parts=[types.Part(text=text)])
    final_text = "(no final response)"

    async for ev in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
        if ev.is_final_response():
            if ev.content and ev.content.parts:
                final_text = ev.content.parts[0].text
            break

    print(f"<<< {final_text}")

# -------------------------
# 4) エントリポイント
# -------------------------
async def main():
    session_service = InMemorySessionService()
    app, user, sid = "multi_tool_demo", "user_1", "sess_001"
    await session_service.create_session(app_name=app, user_id=user, session_id=sid)

    runner = Runner(agent=agent, app_name=app, session_service=session_service)

    # テストクエリ：ツールの使い分けを意図的に変える
    await ask(runner, user, sid, "台北の天気どう？着るものの提案も欲しいです。")
    await ask(runner, user, sid, "1万円をペソに変えるといくら？あとマニラの天気も。")
    await ask(runner, user, sid, "シドニーに行くけど何を着ればいい？")

if __name__ == "__main__":
    asyncio.run(main())