import streamlit as st
import pandas as pd
import os
from lightweight_charts.widgets import StreamlitChart
from Chan import CChan
from ChanConfig import CChanConfig
from Common.CEnum import AUTYPE, DATA_SRC, KL_TYPE

# ================= 默认配置 =================
DEFAULT_CODE = "BTC/USDT"
# ===========================================

st.set_page_config(page_title="真实行情版 5Min", layout="wide")

# === 侧边栏：网络与代理设置 ===
st.sidebar.header("🔌 网络连接设置")
st.sidebar.info("如果您在国内本地运行，必须配置代理才能连接交易所。")

# 常见的代理端口提示
proxy_help = """
常见代理地址(请查看您的软件设置):
- Clash: http://127.0.0.1:7890
- v2rayN: http://127.0.0.1:10809
- Steam++: http://127.0.0.1:9999
"""
use_proxy = st.sidebar.checkbox("开启代理 (VPN)", value=False)
proxy_url = st.sidebar.text_input("代理地址", value="http://127.0.0.1:7890", help=proxy_help)

if use_proxy and proxy_url:
    # 关键步骤：强行让 Python 走代理通道
    os.environ['http_proxy'] = proxy_url
    os.environ['https_proxy'] = proxy_url
    st.sidebar.success(f"已设置代理: {proxy_url}")
else:
    # 清除代理设置，防止干扰
    os.environ.pop('http_proxy', None)
    os.environ.pop('https_proxy', None)

# === 数据获取逻辑 ===
@st.cache_data(ttl=30) # 缩短缓存时间到30秒，看盘更实时
def get_real_data(code):
    config = CChanConfig({
        "bi_strict": True,
        "bi_fx_check": "strict",
        "bi_end_is_peak": True,
        "trigger_step": False,
        "divergence_rate": float("inf"),
        "min_zs_cnt": 0,
    })
    try:
        # DATA_SRC.CCXT 默认会尝试连接 Binance
        chan = CChan(
            code=code,
            data_src=DATA_SRC.CCXT,
            lv_list=[KL_TYPE.K_5M],
            config=config,
            autype=AUTYPE.QFQ,
        )
        if chan[0].lst:
            return chan[0]
        return None
    except Exception as e:
        # 把具体的报错抛出来，方便调试
        raise e

def main():
    st.title(f"📈 {DEFAULT_CODE} 5分钟真实走势")
    
    # 状态提示区
    status_area = st.empty()
    status_area.info("⏳ 正在连接交易所获取数据...")

    try:
        kl_data = get_real_data(DEFAULT_CODE)
        
        if kl_data:
            status_area.success(f"✅ 数据获取成功! 最新时间: {kl_data.lst[-1].lst[-1].time.to_str()}")
            
            # 1. 处理数据
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

            # 2. 绘图
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

        else:
            status_area.error("❌ 获取到了空数据，可能是交易对名称错误或交易所暂无数据。")

    except Exception as e:
        status_area.error(f"❌ 连接失败。")
        st.error(f"详细报错信息: {e}")
        st.warning("""
        **排查建议：**
        1. 请勾选侧边栏的 **'开启代理'**。
        2. 确认您的代理端口号是否正确（Clash默认7890，v2ray默认10809）。
        3. 确保您的 VPN 软件已开启，并且使用的是 **'全局模式'** 或 **'规则模式'**。
        """)

    # 刷新按钮
    if st.button("🔄 刷新数据"):
        st.cache_data.clear()
        st.rerun()

if __name__ == "__main__":
    main()
