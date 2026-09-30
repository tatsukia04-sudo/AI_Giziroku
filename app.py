"""大学の授業向け AI議事録ツール (Streamlit + Gemini API)

ブラウザで録音した音声(または音声ファイル)を Gemini で文字起こしし、
授業ノート形式に要約する。
"""
import io
import os
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
INLINE_LIMIT = 15 * 1024 * 1024  # これを超える音声は Files API 経由で送る

TRANSCRIBE_PROMPT = (
    "この授業の音声を、日本語で正確に文字起こししてください。"
    "フィラー(えー、あのー等)は省き、話題の切れ目で改行してください。"
    "聞き取れない部分は [不明瞭] と書いてください。文字起こし本文のみを出力してください。"
)

SUMMARY_PROMPT = """あなたは大学の授業ノートを作る優秀なアシスタントです。
以下の授業の文字起こしから、Markdown形式で議事録(授業ノート)を作成してください。
文字起こしにない内容は書き足さず、推測した場合は「(推測)」と明記してください。

# 出力形式
## 概要
(3〜5文で授業全体の流れ)
## 要点
(箇条書き。重要度の高い順)
## 重要用語
(用語: 一言説明 の形式)
## 課題・連絡事項
(課題、提出期限、試験・レポート情報。なければ「特になし」)
## 復習・疑問点
(復習すべき点や、授業内で曖昧だった点)

# 授業情報
{meta}

# 文字起こし
{transcript}
"""


def get_key() -> str:
    return (st.session_state.get("api_key") or os.getenv("GEMINI_API_KEY") or "").strip()


def get_client() -> genai.Client | None:
    key = get_key()
    return genai.Client(api_key=key) if key else None


def transcribe(client: genai.Client, audio: bytes, mime: str) -> str:
    if len(audio) <= INLINE_LIMIT:
        part = types.Part.from_bytes(data=audio, mime_type=mime)
    else:
        part = client.files.upload(
            file=io.BytesIO(audio), config=types.UploadFileConfig(mime_type=mime)
        )
    res = client.models.generate_content(model=st.session_state.get("model", MODEL), contents=[TRANSCRIBE_PROMPT, part])
    return (res.text or "").strip()


def summarize(client: genai.Client, transcript: str, meta: str) -> str:
    prompt = SUMMARY_PROMPT.format(meta=meta or "(未入力)", transcript=transcript)
    res = client.models.generate_content(model=st.session_state.get("model", MODEL), contents=prompt)
    return (res.text or "").strip()


def main() -> None:
    st.set_page_config(page_title="AI議事録", page_icon="📝", layout="wide")
    st.title("📝 AI議事録ツール(授業用)")

    ss = st.session_state
    ss.setdefault("segments", [])  # [(bytes, mime)]
    ss.setdefault("transcript", "")
    ss.setdefault("summary", "")

    with st.sidebar:
        st.header("設定")
        ss["api_key"] = st.text_input(
            "Gemini APIキー", type="password", help="ここに貼り付けるだけで使えます(.envの設定は不要)"
        )
        ss["model"] = st.text_input("モデル名", value=MODEL, help="例: gemini-2.5-flash。AI Studioに表示されるモデルIDを入力")
        course = st.text_input("授業名", placeholder="例: 経済学入門")
        topic = st.text_input("今回のテーマ", placeholder="例: 需要と供給")
        st.divider()
        if st.button("最初からやり直す"):
            ss["segments"], ss["transcript"], ss["summary"] = [], "", ""
            st.rerun()

    tab_rec, tab_up, tab_text = st.tabs(["🎙️ 録音", "📁 ファイル", "⌨️ テキスト貼り付け"])

    with tab_rec:
        st.write("録ったら「この録音を追加」を押してください。休憩などで何回かに分けて録音できます。")
        clip = st.audio_input("録音する")
        if clip is not None and st.button("この録音を追加"):
            ss["segments"].append((clip.getvalue(), "audio/wav"))
            st.rerun()

    with tab_up:
        up = st.file_uploader("授業の録音ファイル", type=["mp3", "m4a", "wav", "aac", "ogg", "flac"])
        if up is not None and st.button("このファイルを追加"):
            mime = up.type or "audio/mpeg"
            ss["segments"].append((up.getvalue(), mime))
            st.rerun()

    with tab_text:
        pasted = st.text_area("すでにある文字起こし・メモ", height=200)
        if st.button("この文章を文字起こしとして使う") and pasted.strip():
            ss["transcript"] = pasted.strip()
            ss["summary"] = ""

    if ss["segments"]:
        st.subheader(f"追加済みの音声: {len(ss['segments'])}件")
        for i, (data, mime) in enumerate(ss["segments"], 1):
            st.audio(data, format=mime)
            st.caption(f"#{i} ({len(data) / 1024 / 1024:.1f} MB)")

    key = get_key()
    if key and not key.isascii():
        st.error("APIキーに日本語などが含まれています。.env の GEMINI_API_KEY を、Google AI Studioで発行した英数字のキーに書き換えてください。")
        return
    client = get_client()
    if not client:
        st.info("サイドバーにGemini APIキーを入力してください。")
        return

    if ss["segments"] and st.button("文字起こしを実行", type="primary"):
        try:
            with st.spinner("文字起こし中…"):
                texts = [transcribe(client, d, m) for d, m in ss["segments"]]
            ss["transcript"] = "\n\n".join(texts)
            ss["summary"] = ""
        except Exception as e:  # API/ネットワークエラーを画面に表示
            st.error(f"文字起こしに失敗しました: {e}")

    if ss["transcript"]:
        ss["transcript"] = st.text_area("文字起こし(修正できます)", ss["transcript"], height=250)
        if st.button("要約して議事録を作成", type="primary"):
            meta = "\n".join(
                x for x in [f"授業名: {course}" if course else "", f"テーマ: {topic}" if topic else ""] if x
            )
            try:
                with st.spinner("要約中…"):
                    ss["summary"] = summarize(client, ss["transcript"], meta)
            except Exception as e:
                st.error(f"要約に失敗しました: {e}")

    if ss["summary"]:
        st.divider()
        st.subheader("議事録")
        st.markdown(ss["summary"])
        name = f"{datetime.now():%Y%m%d}_{course or 'notes'}.md"
        st.download_button("Markdownでダウンロード", ss["summary"], file_name=name)


main()
