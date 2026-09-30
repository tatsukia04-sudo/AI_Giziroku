# AI議事録ツール(授業用)

ブラウザで授業を録音(または音声ファイルをアップロード)すると、Gemini API が文字起こしと要約を行い、
「概要・要点・重要用語・課題連絡・復習点」の授業ノートを作ります。

## セットアップ
```bash
pip install -r requirements.txt
cp .env.example .env   # GEMINI_API_KEY を記入(未設定ならアプリ画面で入力可)
streamlit run app.py
```
APIキーは Google AI Studio で取得できます。

## 注意
- 録音前に、担当教員の録音許可を必ず確認してください。
- 録音は Streamlit の `st.audio_input` を使うため、録り終えてから処理する方式です(完全な同時通訳型ではありません)。
