import streamlit as st
import pandas as pd
import plotly.express as px
import datetime
import urllib.parse

st.set_page_config(page_title="チーム野球成績管理システム", layout="wide")

st.title("⚾ チーム・個人成績チェックシステム")
st.write("Googleスプレッドシートから自動連携された最新の成績を表示しています。")

# --- 1. データの読み込み関数（スプレッドシート自動連携） ---
@st.cache_data(ttl=5)
def load_spreadsheet_data():
    # あなたのスプレッドシートID
    sheet_id = "19klE7VorMNWEhSM9zCjYIsiYGxtwY-e6mDC7jGPnmnw"
    
    # 日本語のシート名をURL用に安全に変換（日本語エラー対策）
    sheet_main_encoded = urllib.parse.quote("現在の成績")
    sheet_games_encoded = urllib.parse.quote("試合データ")
    
    # ①「現在の成績」シートの読み込み用URL
    url_main = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_main_encoded}"
    # ②「試合データ」シートの読み込み用URL
    url_games = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_games_encoded}"
    
    # CSVとしてPandasで読み込む
    df_main = pd.read_csv(url_main)
    df_games = pd.read_csv(url_games)
    
    return df_main, df_games

try:
    df_main, df_games = load_spreadsheet_data()
except Exception as e:
    st.error(f"Googleスプレッドシートの読み込みに失敗しました。共有設定やシート名を確認してください。: {e}")
    st.stop()

# --- 2. 画面UIの構築 (サイドバーで条件選択) ---
st.sidebar.header("🔍 表示条件設定")

mode = st.sidebar.radio(
    "表示モードを選択してください：",
    ["🏆 すべての通算成績", "🗓️ 今月の成績", "🌸 春季リーグ戦（スコア自動計算）"]
)

# モードに応じたデータの取得・統合処理
def get_filtered_data(mode, df_main, df_games):
    if mode == "🏆 すべての通算成績":
        y_cols = ["番号","name","打数","安打","塁打数","四死球","三振","企図","成功","犠飛","打点","打率","長打率","出塁率","OPS"]
        p_cols = ["番号_p","name_p","投球回","被安打","与四死球","奪三振","自責点","防御率","被打率","与球率","奪三振率","WHIP"]
        
        df_y = df_main[[c for c in y_cols if c in df_main.columns]].dropna(subset=["name"])
        
        p_exist_cols = [c for c in df_main.columns if c in p_cols or c.replace('_p','') in p_cols]
        if p_exist_cols:
            df_p = df_main[p_exist_cols].dropna(subset=["name_p" if "name_p" in df_main.columns else "name"])
            df_p.columns = [c.replace('_p', '') for c in df_p.columns]
        else:
            df_p = pd.DataFrame()
            
        return df_y, df_p
    
    elif mode == "🗓️ 今月の成績":
        # ひとまず「現在の成績」の通算をそのまま表示（必要に応じて後から月別シートも作れます）
        return df_main, pd.DataFrame()
        
    elif mode == "🌸 春季リーグ戦（スコア自動計算）":
        if df_games.empty or "試合日" not in df_games.columns:
            return pd.DataFrame(), pd.DataFrame()
            
        # 試合日を日付型に変換して4月・5月を抽出
        df_games["試合日"] = pd.to_datetime(df_games["試合日"])
        df_spring = df_games[df_games["試合日"].dt.month.isin([4, 5])]
        
        if df_spring.empty:
            return pd.DataFrame(), pd.DataFrame()
            
        # 野手成績の自動計算
        df_s_y = df_spring.groupby(["選手名"], as_index=False).sum()
        df_s_y = df_s_y.rename(columns={"選手名": "name"})
        df_s_y["番号"] = range(1, len(df_s_y) + 1)
        
        # 数式での自動計算
        df_s_y["打率"] = (df_s_y["安打"] / df_s_y["打数"]).fillna(0)
        if "単打" in df_s_y.columns:
            df_s_y["塁打数"] = df_s_y["単打"] + df_s_y["二塁打"]*2 + df_s_y["三塁打"]*3 + df_s_y["本塁打"]*4
        else:
            df_s_y["塁打数"] = df_s_y["安打"]
            
        df_s_y["長打率"] = (df_s_y["塁打数"] / df_s_y["打数"]).fillna(0)
        df_s_y["出塁率"] = ((df_s_y["安打"] + df_s_y["四死球"]) / (df_s_y["打数"] + df_s_y["四死球"] + df_s_y["犠飛"])).fillna(0)
        df_s_y["OPS"] = df_s_y["出塁率"] + df_s_y["長打率"]
        
        # 投手成績の自動計算
        if "投球回" in df_spring.columns:
            df_s_p = df_spring.groupby(["選手名"], as_index=False).sum()
            df_s_p = df_s_p.rename(columns={"選手名": "name"})
            df_s_p["番号"] = range(1, len(df_s_p) + 1)
            df_s_p["防御率"] = ((df_s_p["自責点"] * 9) / df_s_p["投球回"]).fillna(0)
            df_s_p["WHIP"] = ((df_s_p["被安打"] + df_s_p["与四死球"]) / df_s_p["投球回"]).fillna(0)
            df_s_p["被打率"] = (df_s_p["被安打"] / df_s_p["投球回"]).fillna(0)
            df_s_p["与球率"] = ((df_s_p["与四死球"] * 9) / df_s_p["投球回"]).fillna(0)
            df_s_p["奪三振率"] = ((df_s_p["奪三振"] * 9) / df_s_p["投球回"]).fillna(0)
        else:
            df_s_p = pd.DataFrame()
            
        return df_s_y, df_s_p

df_active_y, df_active_p = get_filtered_data(mode, df_main, df_games)

# 選手・対象リストの作成
all_players = set()
if not df_active_y.empty and "name" in df_active_y.columns: all_players.update(df_active_y["name"].tolist())
if not df_active_p.empty and "name" in df_active_p.columns: all_players.update(df_active_p["name"].tolist())
all_players = sorted(list(all_players))

selected_target = st.sidebar.selectbox(
    "👤 選手・対象を選択してください：",
    ["👥 チーム全体"] + all_players
)

# --- 3. メイン画面の描画 ---
st.header(f"{mode} ── 表示中: {selected_target}")

if selected_target == "👥 チーム全体":
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🔹 野手成績（ランキング順）")
        if not df_active_y.empty:
            df_show_y = df_active_y.sort_values(by="OPS", ascending=False)
            show_cols = [c for c in ["番号","name","打数","安打","打点","打率","長打率","出塁率","OPS"] if c in df_show_y.columns]
            st.dataframe(
                df_show_y[show_cols].style.background_gradient(cmap="YlGn", subset=[c for c in ["打率", "長打率", "出塁率", "OPS"] if c in show_cols])
                                      .format({c: "{:.3f}" for c in ["打率", "長打率", "出塁率", "OPS"] if c in show_cols}), 
                height=600, use_container_width=True
            )
        else:
            st.info("対象の野手データがありません。スプレッドシートの入力内容を確認してください。")
            
    with col2:
        st.subheader("🔸 投手成績（防御率順）")
        if not df_active_p.empty:
            df_show_p = df_active_p.sort_values(by="防御率", ascending=True)
            show_cols_p = [c for c in ["番号","name","投球回","防御率","WHIP","被打率","与球率","奪三振率"] if c in df_show_p.columns]
            st.dataframe(
                df_show_p[show_cols_p].style.background_gradient(cmap="OrRd_r", subset=[c for c in ["防御率", "WHIP"] if c in show_cols_p])
                                      .format({c: "{2}" for c in ["防御率", "WHIP", "与球率", "奪三振率"] if c in show_cols_p}.get("防御率", "{:.2f}")) # 安全なフォーマット
                                      .format({"防御率": "{:.2f}", "WHIP": "{:.2f}", "与球率": "{:.2f}", "奪三振率": "{:.2f}", "被打率": "{:.3f}"}), 
                height=600, use_container_width=True
            )
        else:
            st.info("対象の投手データがありません。")

else:
    # === 個人成績 ＋ レーダーチャート画面 ===
    p_y = df_active_y[df_active_y["name"] == selected_target] if not df_active_y.empty else pd.DataFrame()
    p_p = df_active_p[df_active_p["name"] == selected_target] if not df_active_p.empty else pd.DataFrame()
    
    if p_y.empty and p_p.empty:
        st.warning("選択された期間にこの選手のデータはありません。")
    else:
        col_data, col_graph = st.columns([4, 3])
        
        with col_data:
            if not p_y.empty:
                st.subheader("⚾ 野手個人スタッツ")
                st.dataframe(p_y.style.format({c: "{:.3f}" for c in ["打率", "長打率", "出塁率", "OPS"] if c in p_y.columns}), use_container_width=True)
                
            if not p_p.empty:
                st.subheader("🥎 投手個人スタッツ")
                st.dataframe(p_p.style.format({c: "{:.2f}" for c in ["防御率", "WHIP", "与球率", "奪三振率"] if c in p_p.columns}).format({"被打率": "{:.3f}" if "被打率" in p_p.columns else "{}"}), use_container_width=True)
                
        with col_graph:
            st.subheader("📊 選手能力レーダーチャート")
            
            if not p_y.empty:
                row = p_y.iloc[0]
                stats = {
                    "打率(ミート)": min(row.get("打率", 0) / 0.400, 1.0),
                    "長打率(パワー)": min(row.get("長打率", 0) / 0.600, 1.0),
                    "出塁率(選球眼)": min(row.get("出塁率", 0) / 0.450, 1.0),
                    "OPS(貢献度)": min(row.get("OPS", 0) / 1.000, 1.0),
                    "打点(勝負強さ)": min(row.get("打点", 0) / 15, 1.0)
                }
                df_graph = pd.DataFrame(dict(r=list(stats.values()), theta=list(stats.keys())))
                fig = px.line_polar(df_graph, r='r', theta='theta', line_close=True, range_r=[0,1])
                fig.update_traces(fill='toself', line_color="#2E7D32")
                fig.update_layout(polar=dict(radialaxis=dict(visible=True, showticklabels=False)), margin=dict(l=40, r=40, t=40, b=40))
                st.plotly_chart(fig, use_container_width=True)
                
            elif not p_p.empty:
                row = p_p.iloc[0]
                stats_p = {
                    "防御率(安定感)": max(0.0, min(1.0, (6.0 - row.get("防御率", 0)) / 6.0)),
                    "WHIP(支配力)": max(0.0, min(1.0, (2.0 - row.get("WHIP", 0)) / 2.0)),
                    "与球率(制球力)": max(0.0, min(1.0, (5.0 - row.get("与球率", 0)) / 5.0)),
                    "奪三振率(キレ)": min(row.get("奪三振率", 0) / 10.0, 1.0)
                }
                df_graph = pd.DataFrame(dict(r=list(stats_p.values()), theta=list(stats_p.keys())))
                fig = px.line_polar(df_graph, r='r', theta='theta', line_close=True, range_r=[0,1])
                fig.update_traces(fill='toself', line_color="#EF6C00")
                fig.update_layout(polar=dict(radialaxis=dict(visible=True, showticklabels=False)), margin=dict(l=40, r=40, t=40, b=40))
                st.plotly_chart(fig, use_container_width=True)