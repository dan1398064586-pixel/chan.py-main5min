import streamlit as st
import pandas as pd
import yfinance as yf  # <--- 关键改变：用雅虎财经代替交易所接口
import os
from lightweight_charts.widgets import StreamlitChart
from Chan import CChan
from ChanConfig import CChanConfig
from Common.CEnum import AUTYPE, DATA_SRC, KL_TYPE

# ================= 配置 =================
# 雅虎财经的代码格式：BTC-USD
CODE_YF = "BTC-USD" 
# 缠论计算用的代码（对应生成的CSV文件名）
CODE_CSV = "BTC_YF_DATA" 
TARGET_LV = KL_TYPE.K_5M
# =======================================

st.set_page_config(page_title="BTC 5分钟 (云端直连版)", layout="wide")

def fetch_and_save_data():
    """
    从雅虎财经获取数据，并转换成 chan.py 能识别的 CSV 格式
    """
    try:
        # 1. 下载数据 (最近 5 天的 5 分钟数据)
        # 雅虎财经在美国云端可以直接访问，无需 VPN
        df = yf.download(CODE_YF, period="5d", interval="5m", progress=False)
        
        if df.empty:
            return False

        # 2. 格式清洗
        df = df.reset_index()
        # 雅虎的时间是 UTC，我们转成字符串即可，chan.py 会处理
        # 重命名列以符合 chan.py 的 CSV 读取标准
        # 雅虎列名: Date, Open, High, Low, Close, Volume
        # chan.py CSV需要: time, open, high, low, close, volume
        
        # 展平多层索引（如果存在）
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        rename_dict = {
            "Datetime": "time", 
            "Date": "time",
            "Open": "open",
            "High": "high",
            "Low": "low", 
            "Close": "close",
            "Volume": "volume"
        }
        df = df.rename(columns=rename_dict)
        
        # 确保包含所需的列
        needed_cols = ['time', 'open', 'high', 'low', 'close', 'volume']
        # 过滤掉非交易时间可能的空值
        df = df.dropna(subset=needed_cols)
        
        # 3. 保存为临时 CSV 文件
        # chan.py 的 DATA_SRC.CSV 模式会读取 code + ".csv"
        csv_filename = f"{CODE_CSV}.csv"
        # 这里的路径通常是根目录，或者 Data 目录，我们直接存根目录并在 DataAPI 里兼容，
        # 或者最简单的方法：chan.py 默认可能在特定目录找，但 main.py 示例是直接读取。
        # 为了保险，我们保存到当前脚本同级目录
        df[needed_cols].to_csv(csv_filename, index=False)
        return True
        
    except Exception as e:
        st.error(f"雅虎数据获取失败: {e}")
        return False

@st.cache_data(ttl=60) # 1分钟刷新一次
def get_chan_data():
    # 1. 先去下载最新数据存为 CSV
    success = fetch_and_save_data()
    if not success:
        return None

    # 2. 让 Chan.py 读取这个 CSV
    config = CChanConfig({
        "bi_strict": True,
        "bi_fx_check": "strict",
        "bi_end_is_peak": True,
        "trigger_step": False,
        "divergence_rate": float("inf"),
        "min_zs_cnt": 0,
    })
    
    try:
        # DATA_SRC.CSV 模式下，code 参数对应文件名（不带.csv后缀）
        chan = CChan(
            code=CODE_CSV,          # 读取 BTC_YF_DATA.csv
            data_src=DATA_SRC.CSV,  # 指定模式为 CSV
            lv_list=[TARGET_LV],
            config=config,
            autype=AUTYPE.QFQ,
        )
        return chan[0] if chan[0].lst else None
    except Exception as e:
        st.error(f"缠论计算出错: {e}")
        return None

def main():
    st.markdown(f"### 📈 {CODE_YF} 5分钟 - 云端直连版")
    st.caption("数据源: Yahoo Finance (无需VPN，云端可用)")

    kl_data = get_chan_data()
    
    if kl_data:
        # === 数据转换 (保持原版逻辑) ===
        k_list = []
        for klu in kl_data.lst:
            for unit_klu in klu.lst:
                k_list.append({
                    'time': unit_klu.time.to_str(),
                    'open': float(unit_klu.open),
                    'high': float(unit_klu.high),
                    'low': float(unit_klu.low),
                    'close': float(unit_klu.close),
                })
        df_k = pd.DataFrame(k_list).drop_duplicates(subset=['time'], keep='last')

        bi_list = []
        if kl_data.bi_list:
            bi_list.append({'time': kl_data.bi_list[0].get_begin_klu().time.to_str(), 'value': float(kl_data.bi_list[0].get_begin_val())})
            for bi in kl_data.bi_list:
                bi_list.append({'time': bi.get_end_klu().time.to_str(), 'value': float(bi.get_end_val())})
        df_bi = pd.DataFrame(bi_list).drop_duplicates(subset=['time'], keep='last')

        seg_list = []
        if kl_data.seg_list:
            seg_list.append({'time': kl_data.seg_list[0].start_bi.get_begin_klu().time.to_str(), 'value': float(kl_data.seg_list[0].start_bi.get_begin_val())})
            for seg in kl_data.seg_list:
                seg_list.append({'time': seg.end_bi.get_end_klu().time.to_str(), 'value': float(seg.end_bi.get_end_val())})
        df_seg = pd.DataFrame(seg_list).drop_duplicates(subset=['time'], keep='last')

        # === 绘图 ===
        chart = StreamlitChart(height=600)
        chart.layout(background_color='#f5d695', text_color='black')
        chart.grid(vert_enabled=False, horz_enabled=False)
        chart.time_scale(min_bar_spacing=0.02)
        chart.legend(visible=True, font_size=14)

        chart.set(df_k)
        
        if not df_bi.empty:
            line_bi = chart.create_line(name='Bi (笔)', color='#f23645', width=2)
            line_bi.set(df_bi)
        
        if not df_seg.empty:
            line_seg = chart.create_line(name='Seg (线段)', color='blue', width=3)
            line_seg.set(df_seg)

        chart.load()

        # 显示最新价格
        last_price = df_k.iloc[-1]['close']
        last_time = df_k.iloc[-1]['time']
        st.success(f"✅ 最新价格: {last_price:.2f} (更新于 {last_time})")

    else:
        st.warning("数据加载中或获取失败，请尝试点击刷新...")

    if st.button("🔄 刷新数据"):
        st.cache_data.clear()
        st.rerun()

if __name__ == "__main__":
    main()
