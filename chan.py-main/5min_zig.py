import pandas as pd
from lightweight_charts import Chart
from Chan import CChan
from ChanConfig import CChanConfig
from Common.CEnum import AUTYPE, DATA_SRC, KL_TYPE

# ================= 配置 =================
code = "BTC/USDT"
target_lv = KL_TYPE.K_5M  # 可改为 K_5M, K_30M 等
NAME_BI = 'Bi'
NAME_SEG = 'Seg'
# =======================================

print("=== 1. 程序启动，正在初始化... ===")

def format_time(t):
    # 格式化 CTime 对象为字符串
    return f"{t.year:04}-{t.month:02}-{t.day:02} {t.hour:02}:{t.minute:02}"

def get_data_once():
    print("=== 2. 开始连接数据源下载数据... ===")
    config = CChanConfig({
        "bi_strict": True, 
        "bi_fx_check": "strict", 
        "bi_end_is_peak": True,
        "trigger_step": False, 
        "skip_step": 0, 
        "divergence_rate": float("inf"), 
        "min_zs_cnt": 0,
    })
    
    try:
        # 尝试导入 ccxt 检查是否安装
        import ccxt
    except ImportError:
        print("!!! 错误: 未安装 ccxt 库。请运行: pip install ccxt")
        return None

    try:
        chan = CChan(
            code=code, 
            begin_time=None, 
            end_time=None, 
            data_src=DATA_SRC.CCXT, 
            lv_list=[target_lv], 
            config=config, 
            autype=AUTYPE.QFQ,
        )
        # 检查是否有数据
        if not chan[0].lst:
            print("!!! 警告: 下载成功但数据为空，请检查代码或网络。")
            return None
        return chan[0]
    except Exception as e:
        print(f"!!! 数据下载/计算失败: {e}")
        return None

if __name__ == "__main__":
    # 1. 获取数据
    kl_data = get_data_once()
    
    if not kl_data:
        print("!!! 程序因无数据退出。")
        exit()

    print(f"=== 3. 数据获取成功 (共 {len(kl_data.lst)} 根K线)，正在处理... ===")
    
    # 2. 处理 K 线数据
    k_list = []
    # 展开合并K线(CKLine)中的原始K线(CKLine_Unit)
    for klu in kl_data.lst: 
        for unit_klu in klu.lst:
            k_list.append({
                'time': format_time(unit_klu.time), 
                'open': float(unit_klu.open),
                'high': float(unit_klu.high),
                'low': float(unit_klu.low),
                'close': float(unit_klu.close),
                'volume': float(unit_klu.trade_info.metric.get('volume', 0))
            })
    df_k = pd.DataFrame(k_list)
    # 去重，防止同一时间戳有多条数据
    df_k.drop_duplicates(subset=['time'], keep='last', inplace=True)

    # 3. 处理 笔 (去重逻辑)
    bi_list = []
    if kl_data.bi_list:
        # 添加第一笔的起始点
        first_bi = kl_data.bi_list[0]
        bi_list.append({'time': format_time(first_bi.get_begin_klu().time), NAME_BI: float(first_bi.get_begin_val())})
        # 后续只添加每笔的结束点，因为上一笔结束 = 下一笔开始
        for bi in kl_data.bi_list:
            bi_list.append({'time': format_time(bi.get_end_klu().time), NAME_BI: float(bi.get_end_val())})
    df_bi = pd.DataFrame(bi_list)
    # 再次确保无重复时间
    if not df_bi.empty:
        df_bi.drop_duplicates(subset=['time'], keep='last', inplace=True)

    # 4. 处理 线段 (去重逻辑)
    seg_list = []
    if kl_data.seg_list:
        # 添加第一段的起始点
        first_seg = kl_data.seg_list[0]
        seg_list.append({'time': format_time(first_seg.start_bi.get_begin_klu().time), NAME_SEG: float(first_seg.start_bi.get_begin_val())})
        # 后续只添加结束点
        for seg in kl_data.seg_list:
            seg_list.append({'time': format_time(seg.end_bi.get_end_klu().time), NAME_SEG: float(seg.end_bi.get_end_val())})
    df_seg = pd.DataFrame(seg_list)
    if not df_seg.empty:
        df_seg.drop_duplicates(subset=['time'], keep='last', inplace=True)

    print("=== 4. 正在启动图表窗口... ===")
    
    # 5. 启动图表
    chart = Chart(toolbox=True)
    chart.legend(True)
    chart.layout(background_color='#f5d695', text_color='black')
    chart.grid(vert_enabled=False, horz_enabled=False)
    # 调整 K 线显示比例
    chart.time_scale(min_bar_spacing=0.02)
    
    # 创建线条
    line_bi = chart.create_line(name=NAME_BI, color='#f23645', width=2)
    line_seg = chart.create_line(name=NAME_SEG, color='blue', width=3)
    
    # 设置数据 (确保不为空)
    if not df_k.empty: 
        chart.set(df_k)
    
    if not df_bi.empty:
        # 只保留在 K 线时间范围内的数据，防止图表压缩
        line_bi.set(df_bi)
        
    if not df_seg.empty:
        line_seg.set(df_seg)
    
    print("=== 5. 图表已加载，请查看弹出的窗口 ===")
    print("    (提示: 如果使用 VPN，请确保 ccxt 能正常访问币安 API)")
    chart.show(block=True)