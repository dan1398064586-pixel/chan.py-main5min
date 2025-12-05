# 文件路径: chan.py-main/5min_zig_cloud.py
import streamlit as st
import pandas as pd
# 关键修改：从 widgets 导入 StreamlitChart，而不是原来的 Chart
from lightweight_charts.widgets import StreamlitChart
from Chan import CChan
from ChanConfig import CChanConfig
from Common.CEnum import AUTYPE, DATA_SRC, KL_TYPE

# ================= 配置 =================
CODE = "BTC/USDT"
TARGET_LV = KL_TYPE.K_5M
# =======================================

# 设置网页为宽屏模式，手机横屏看体验更好
st.set_page_config(page_title="Chan.py 5Min Zig", layout="wide")

# 缓存数据获取函数，防止手机刷新时重复请求交易所
@st.cache_data(ttl=60)
def get_kl_data_cached():
    config = CChanConfig({
        "bi_strict": True,
        "bi_fx_check": "strict",
        "bi_end_is_peak": True,
        "trigger_step": False,
        "divergence_rate": float("inf"),
        "min_zs_cnt": 0,
    })
    try:
        chan = CChan(
            code=CODE,
            begin_time=None,
            end_time=None,
            data_src=DATA_SRC.CCXT,
            lv_list=[TARGET_LV],
            config=config,
            autype=AUTYPE.QFQ,
        )
        return chan[0] if chan[0].lst else None
    except Exception as e:
        st.error(f"数据获取失败: {e}")
        return None

def main():
    st.markdown(f"### 📈 {CODE} 5分钟 - 5min_zig 风格复刻版")
    
    # 1. 获取数据
    kl_data = get_kl_data_cached()
    if not kl_data:
        st.warning("未获取到数据，请检查网络 (需访问交易所 API)")
        return

    # 2. 数据转换 (保持和原版一致的逻辑)
    k_list = []
    for klu in kl_data.lst:
        for unit_klu in klu.lst:
            k_list.append({
                'time': unit_klu.time.to_str(), # lightweight_charts 需要字符串或时间戳
                'open': float(unit_klu.open),
                'high': float(unit_klu.high),
                'low': float(unit_klu.low),
                'close': float(unit_klu.close),
                'volume': float(unit_klu.trade_info.metric.get('volume', 0))
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

    # 3. 创建图表 (关键步骤：使用 StreamlitChart)
    # height可以根据手机屏幕调整，600在手机竖屏也够用
    chart = StreamlitChart(height=600)
    
    # === 完美复刻原版 5min_zig.py 的样式 ===
    chart.layout(background_color='#f5d695', text_color='black') # 您的经典淡黄配色
    chart.grid(vert_enabled=False, horz_enabled=False)
    chart.time_scale(min_bar_spacing=0.02)
    chart.legend(visible=True, font_size=14)

    # 4. 绘制线条
    # K线
    chart.set(df_k)
    
    # 笔 (Bi) - 红色
    line_bi = chart.create_line(name='Bi (笔)', color='#f23645', width=2)
    line_bi.set(df_bi)
    
    # 线段 (Seg) - 蓝色
    line_seg = chart.create_line(name='Seg (线段)', color='blue', width=3)
    line_seg.set(df_seg)

    # 5. 加载图表 (原版是 chart.show(), 这里用 chart.load())
    chart.load()

    # 刷新按钮
    if st.button("🔄 刷新最新行情"):
        st.cache_data.clear()
        st.rerun()

if __name__ == "__main__":
    main()