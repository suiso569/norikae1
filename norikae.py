import streamlit as st
import networkx as nx

# ==========================================
# 1. 路線データの定義
# ==========================================
def get_lines_data():
    return {
        "中央線": [("一ノ瀬", "境港", 120), ("境港", "谷上町", 60), ("谷上町", "第1拠点", 30), ("第1拠点", "晴海坂", 30), ("晴海坂", "滝沢", 90), ("滝沢", "終宮", 120), ("終宮", "新蒼海宮", 120), ("新蒼海宮", "蒼海宮", 60)],
        "桜町線(各停)": [("荒山村", "桜町一丁目", 60), ("桜町一丁目", "谷上三丁目", 30), ("谷上三丁目", "白浜崎", 60), ("白浜崎", "砂炭江", 90), ("砂炭江", "霧ヶ峰", 90), ("霧ヶ峰", "霧ヶ峰湖", 60), ("霧ヶ峰湖", "風見野", 120), ("風見野", "北茜ヶ原", 120), ("北茜ヶ原", "茜ヶ原", 60)],
        "桜町線(快速)": [("白浜崎", "霧ヶ峰", 180), ("霧ヶ峰", "茜ヶ原", 360)],
        "東西線": [("一ノ瀬", "桜坂", 180), ("桜坂", "緑山", 180), ("緑山", "旭ヶ丘", 60), ("旭ヶ丘", "霧ヶ峰", 90), ("霧ヶ峰", "亀浜", 60)],
        "南北線": [("西霧ヶ峰", "新都町", 30), ("新都町", "前哨基地", 180)],
        "霧ヶ峰線": [("蒼海宮", "亀浜", 150), ("亀浜", "西霧ヶ峰", 30), ("西霧ヶ峰", "霧ヶ峰湖", 60)],
        "新都心線": [("終宮", "亀浜", 130), ("亀浜", "新都町", 60), ("新都町", "朝凪", 60)],
        "中央都市線": [("速見", "霧ヶ峰", 60), ("霧ヶ峰", "西霧ヶ峰", 30), ("西霧ヶ峰", "南新都町", 60), ("南新都町", "朝凪南", 60), ("朝凪南", "朝凪", 60)],
        "南辺線": [("風見野", "前哨基地", 150)],
        "中央新幹線": [("白浜崎", "新蒼海宮", 50)],
        "晴海坂線": [("砂炭江", "晴海坂", 120), ("晴海坂", "東晴海坂", 60)]
    }

# ==========================================
# 2. グラフの構築（状態空間モデル）
# ==========================================
@st.cache_resource
def build_routing_graph():
    G = nx.Graph()
    lines = get_lines_data()
    station_lines = {} # { "駅名": set("路線A", "路線B") }

    # 通常の路線エッジを追加
    for line_name, edges in lines.items():
        for u, v, w in edges:
            u_node = f"{u}|{line_name}"
            v_node = f"{v}|{line_name}"
            
            # 快速優先: アルゴリズムが快速を好むよう、内部コストを微小(-0.1)に削る
            opt_w = w - 0.1 if "快速" in line_name else w
            G.add_edge(u_node, v_node, time=w, weight_fast=opt_w, weight_trans=w, line=line_name, is_transfer=False)
            
            station_lines.setdefault(u, set()).add(line_name)
            station_lines.setdefault(v, set()).add(line_name)

    # 同一駅での乗り換えエッジを追加
    for station, slines in station_lines.items():
        slines = list(slines)
        for i in range(len(slines)):
            for j in range(i+1, len(slines)):
                u_node = f"{station}|{slines[i]}"
                v_node = f"{station}|{slines[j]}"
                # 最速ルートでは標準乗換30秒、乗換最小ルートでは超巨大ペナルティ(10000秒)
                G.add_edge(u_node, v_node, time=30, weight_fast=30, weight_trans=10000, line="🔄 乗換", is_transfer=True)

    # 徒歩連絡エッジ
    walks = [
        ("谷上町", "中央線", "谷上三丁目", "桜町線(各停)", 30),
        ("新都町", "南北線", "南新都町", "中央都市線", 30),
        ("新都町", "新都心線", "南新都町", "中央都市線", 30)
    ]
    for u, ul, v, vl, w in walks:
        G.add_edge(f"{u}|{ul}", f"{v}|{vl}", time=w, weight_fast=w, weight_trans=10000, line="🚶 徒歩連絡", is_transfer=True)

    # 砂炭江の直通運転 (ポイント分岐により乗換不要＝ペナルティ0のエッジ)
    G.add_edge("砂炭江|桜町線(各停)", "亀浜|東西線", time=120, weight_fast=120, weight_trans=120, line="桜町線⇔東西線(直通)", is_transfer=False)
    G.add_edge("砂炭江|桜町線(各停)", "亀浜|新都心線", time=120, weight_fast=120, weight_trans=120, line="桜町線⇔新都心線(直通)", is_transfer=False)
    G.add_edge("砂炭江|桜町線(各停)", "西霧ヶ峰|南北線", time=120, weight_fast=120, weight_trans=120, line="桜町線⇔南北線(直通)", is_transfer=False)

    return G, station_lines, lines

# ==========================================
# 3. メインUIと探索ロジック
# ==========================================
def main():
    st.set_page_config(page_title="Minecraft鉄道 乗り換え案内", layout="centered")
    st.title("Minecraft鉄道 乗り換え案内 🛤️")
    
    G_base, station_lines, lines_data = build_routing_graph()
    unique_stations = sorted(list(station_lines.keys()))

    # --- 検索フォーム ---
    st.markdown("### 出発・到着駅と条件を選択")
    col1, col2 = st.columns(2)
    with col1:
        start_station = st.selectbox("出発駅", unique_stations, index=unique_stations.index("一ノ瀬"))
    with col2:
        end_station = st.selectbox("到着駅", unique_stations, index=unique_stations.index("亀浜"))

    search_mode = st.radio("優先する条件", ["最速（時間を優先）", "乗り換え回数（乗換の少なさを優先）"], horizontal=True)

    if st.button("経路を検索", type="primary", use_container_width=True):
        if start_station == end_station:
            st.warning("出発駅と到着駅が同じです。")
            return

        # 探索用のグラフをコピーし、仮想のSTART/ENDノードを配置
        G = G_base.copy()
        for node in G_base.nodes():
            if node.startswith(f"{start_station}|"):
                G.add_edge("START", node, time=0, weight_fast=0, weight_trans=0, line="乗車", is_transfer=False)
            if node.startswith(f"{end_station}|"):
                G.add_edge(node, "END", time=0, weight_fast=0, weight_trans=0, line="降車", is_transfer=False)
                
        weight_key = "weight_fast" if search_mode == "最速（時間を優先）" else "weight_trans"
        
        try:
            path = nx.shortest_path(G, source="START", target="END", weight=weight_key)
            
            # 結果の集計
            steps = []
            real_time = 0
            transfer_count = 0
            
            for i in range(1, len(path)-2): # STARTとENDを除外して走査
                u, v = path[i], path[i+1]
                edge = G[u][v]
                real_time += edge['time']
                if edge['is_transfer']: transfer_count += 1
                
                u_sta = u.split('|')[0]
                v_sta = v.split('|')[0]
                
                # 同じ路線が続く場合はまとめる処理
                if steps and not edge['is_transfer'] and steps[-1]['line'] == edge['line']:
                    steps[-1]['to'] = v_sta
                    steps[-1]['time'] += edge['time']
                else:
                    steps.append({
                        "from": u_sta, "to": v_sta,
                        "line": edge['line'], "time": edge['time'], "is_transfer": edge['is_transfer']
                    })
            
            # 検索結果の表示
            st.success(f"⏱️ 所要時間: **{real_time // 60}分 {real_time % 60}秒** 🔄 乗換: **{transfer_count}回**")
            st.divider()
            
            # 経路の出力
            st.markdown("### 🗺️ 経路案内")
            st.markdown(f"**🟢 {steps[0]['from']}**")
            
            for step in steps:
                if step['is_transfer']:
                    st.markdown(f" *({step['line']})*")
                else:
                    m, s = divmod(step['time'], 60)
                    time_str = f"{m}分{s}秒" if m > 0 else f"{s}秒"
                    st.info(f"⬇️ **{step['line']}** （{time_str}）")
                
                st.markdown(f"**🔵 {step['to']}**")
                
            st.markdown("🏁 **到着**")

        except nx.NetworkXNoPath:
            st.error("経路が見つかりませんでした。路線の接続が切れている可能性があります。")

    st.divider()
    
    # --- 路線図ビューア（駅名ズラッと表示機能） ---
    st.markdown("### 🚉 路線図ビューア")
    selected_line = st.selectbox("路線を選択して駅一覧を表示", list(lines_data.keys()))
    
    # 選ばれた路線の駅名を順に並べる
    line_stations = []
    for u, v, w in lines_data[selected_line]:
        if not line_stations:
            line_stations.append(u)
        line_stations.append(v)
    
    # 矢印で繋いで表示
    st.markdown(f"**{selected_line} の駅一覧:**")
    st.write(" ➔ ".join(line_stations))

if __name__ == "__main__":
    main()