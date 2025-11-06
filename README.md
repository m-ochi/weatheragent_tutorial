# Google ADKのデモ用アプリ
都市の天気を調べ、適した服装を提案する

# 準備
1. uv(pipとかvenvのような役割をする)のインストール
`pip install uv`
1. Githubプロジェクトのクローン
 https://github.com/m-ochi/weatheragent_tutorial
 - git cloneしてください
`cd weatheragent_tutorial`

1. 必要なモジュールのインストール
`uv sync`
1. 仮想環境のアクティベート
`. .venv/bin/activate`
1. エディタ（vs code）の設定（特にこだわりがなければする必要なし）
1. Gemini API keyの取得
 https://ai.google.dev/gemini-api/docs?hl=ja
 で、Gemini API keyの取得
1. 外部APIの登録とkeyの取得
  1. 天気を教えてくれるAPI
    https://www.weatherapi.com/
  1. 為替を教えてくれるAPI
    https://www.exchangerate-api.com/
1. それぞれのAPIキーをconfig.ymlに書く
1. プログラムの中身を確認し、実行
`python3 main.py`
