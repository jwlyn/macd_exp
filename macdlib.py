import numpy as np
import pandas as pd
from futu import *
from pandas import DataFrame
from itertools import groupby
from operator import itemgetter
import config


class KL_Period(object):
    KL_60 = "KL_60"
    KL_30 = "KL_30"
    KL_15 = "KL_15"


K_LINE_TYPE = {
    KL_Period.KL_60: KLType.K_60M,
    KL_Period.KL_30: KLType.K_30M,
    KL_Period.KL_15: KLType.K_15M,
}


class WaveType(object):
    RED_TOP = 2  # 红柱高峰
    RED_BOTTOM = 1  # 红柱峰底

    GREEN_TOP = -2  # 绿柱波峰
    GREEN_BOTTOM = -1  # 绿柱波底，乳沟深V的尖


def ema(data, n=12, val_name="close"):
    import numpy as np
    '''
        指数平均数指标 Exponential Moving Average
        Parameters
        ------
          data:pandas.DataFrame
                      通过 get_h_data 取得的数据
          n:int
                      移动平均线时长，时间单位根据data决定
          val_name:string
                      计算哪一列的列名，默认为 close 
        return
        -------
          EMA:numpy.ndarray<numpy.float64>
              指数平均数指标
    '''

    prices = []

    EMA = []

    for index, row in data.iterrows():
        if index == 0:
            past_ema = row[val_name]
            EMA.append(row[val_name])
        else:
            # Y=[2*X+(N-1)*Y’]/(N+1)
            today_ema = (2 * row[val_name] + (n - 1) * past_ema) / (n + 1)
            past_ema = today_ema

            EMA.append(today_ema)

    return np.asarray(EMA)


def macd(data, quick_n=12, slow_n=26, dem_n=9, val_name="close"):
    import numpy as np
    '''
        指数平滑异同平均线(MACD: Moving Average Convergence Divergence)
        Parameters
        ------
          data:pandas.DataFrame
                      通过 get_h_data 取得的
          quick_n:int
                      DIFF差离值中快速移动天数
          slow_n:int
                      DIFF差离值中慢速移动天数
          dem_n:int
                      DEM讯号线的移动天数
          val_name:string
                      计算哪一列的列名，默认为 close 
        return
        -------
          OSC:numpy.ndarray<numpy.float64>
              MACD bar / OSC 差值柱形图 DIFF - DEM
          DIFF:numpy.ndarray<numpy.float64>
              差离值
          DEM:numpy.ndarray<numpy.float64>
              讯号线
    '''

    ema_quick = np.asarray(ema(data, quick_n, val_name))
    ema_slow = np.asarray(ema(data, slow_n, val_name))
    DIFF = ema_quick - ema_slow
    data["diff"] = DIFF
    DEM = ema(data, dem_n, "diff")
    BAR = (DIFF - DEM) * 2
    # data['dem'] = DEM
    # data['bar'] = BAR
    return DIFF, DEM, BAR


def ma(data, n=10, val_name="close"):
    '''
    移动平均线 Moving Average
    Parameters
    ------
      data:pandas.DataFrame
                  通过 get_h_data 取得的股票数据
      n:int
                  移动平均线时长，时间单位根据data决定
      val_name:string
                  计算哪一列的列名，默认为 close 收盘值
    return
    -------
      list
          移动平均线
    '''

    values = []
    MA = []

    for index, row in data.iterrows():
        values.append(row[val_name])
        if len(values) == n:
            del values[0]

        MA.append(np.average(values))

    return np.asarray(MA)


def find_successive_bar_areas(df:DataFrame, field='bar'):
    """
    改进的寻找连续区域算法
    :param raw_df:
    :param field:
    :param min_area_width:
    :return:
    """
    successive_areas = []
    # 第一步：把连续的同一颜色区域的index都放入一个数组
    arrays = [df[df[field]>=0].index.array, df[df[field]<=0].index.array]
    for arr in arrays:
        successive_area = []
        for k, g in groupby(enumerate(arr), lambda iv : iv[0] - iv[1]):
            index_group = list(map(itemgetter(1), g))
            successive_area.append((min(index_group), max(index_group)))
        successive_areas.append(successive_area)

    return successive_areas[0], successive_areas[1] # 分别是红色和绿色的区间


def today():
    """

    :return:
    """
    tm_now = datetime.now()
    td = tm_now.strftime("%Y-%m-%d")
    return td


def n_days_ago(n_days):
    """

    :param n_days:
    :return:
    """
    tm_now = datetime.now()
    delta = timedelta(days=n_days)
    tm_start = tm_now - delta
    ago = tm_start.strftime("%Y-%m-%d")
    return ago


def prepare_csv_data(code_list):
    """

    :param code_list: 股票列表
    :return:
    """
    quote_ctx = OpenQuoteContext(host=config.futuapi_address, port=config.futuapi_port)
    for code in code_list:
        for _, ktype in K_LINE_TYPE.items():
            ret, df, page_req_key = quote_ctx.request_history_kline(code, start=n_days_ago(30), end=today(),
                                                                    ktype=ktype,
                                                                    fields=[KL_FIELD.DATE_TIME, KL_FIELD.CLOSE],
                                                                    max_count=1000)
            csv_file_name = df_file_name(code, ktype)
            df.to_csv(csv_file_name)
            time.sleep(3.1)  # 频率限制


def df_file_name(stock_code, ktype):
    """

    :param stock_code:
    :param ktype:
    :return:
    """
    return f'data/{stock_code}_{ktype}.csv'


def compute_df_bar(code_list):
    """
    计算60,30,15分钟的指标，存盘
    :param df:
    :return:
    """
    for code in code_list:
        for k, ktype in K_LINE_TYPE.items():
            csv_file_name = df_file_name(code, ktype)
            df = pd.read_csv(csv_file_name, index_col=0)
            diff, dem, bar = macd(df)
            df['macd_bar'] = bar  # macd
            df['ma5'] = ma(df, 5)
            df['ma10'] = ma(df, 10)
            df['em_bar'] = (df['ma5'] - df['ma10']).apply(lambda val: round(val, 2))  # 均线
            df.to_csv(csv_file_name)


def do_bar_wave_tag(raw_df: DataFrame, field, successive_bar_area, moutain_min_width=5):
    """
    # TODO 试一下FFT寻找波谷波峰
    :param raw_df:
    :param field:
    :param successive_bar_area: 想同样色柱子区域, [tuple(start, end)]
    :param moutain_min_width: 作为一个山峰最小的宽度，否则忽略
    :return: 打了tag 的df副本
    """
    df = raw_df.copy()
    tag_field = f'_{field}'
    df[tag_field] = 0  # 初始化为0
    df[field] = df[field].abs()  # 变成正值处理
    for start, end in successive_bar_area:  # 找到s:e这一段里的所有波峰
        sub_area_list = [(start, end)]
        print(f"--------------------------{start} ~ {end}")
        for s, e in sub_area_list:  # 产生的破碎的连续区间加入这个list里继续迭代直到为空
            if e - s + 1 < moutain_min_width:  # 山峰的宽度太窄，可以忽略
                continue
            # 找到最大柱子，在df上打标
            print(f'{s} -> {e}', end='=====:')
            max_row_index = df.iloc[s:e + 1][field].idxmax(axis=0)  # 寻找规定的行范围的某列最大（小）值的索引
            # 先不急于设置为波峰，因为还需要判断宽度是否符合要求
            # 从这根最大柱子向两侧扫描，直到波谷
            arr = df.iloc[s:e + 1][field].array  # 扫描这个数组
            # 从min_index先向左侧扫
            arr_min_index = max_row_index - s  # 映射到以0开始的数组下标上
            print(f">{max_row_index}<", end=':')
            i = j = 0
            for i in range(arr_min_index, 1, -1):  # 向左侧扫描, 下标是[arr_min_index, 2]
                if arr[i] >= arr[i - 1] or arr[i] >= arr[i - 2]:
                    if i==2:
                        i =0
                        break
                    else:
                        continue
                else:
                    break  # i 就是左侧波谷
            #[0,8], ix=7, j in [7, 7]
            # 从min_index向右侧扫描
            for j in range(arr_min_index, e - s - 1):  # 下标范围是[arr_min_index, len(arr)-2]
                if arr[j] >= arr[j + 1] or arr[j] >= arr[j + 2]:
                    if j==e-s-2:
                        j = e-s
                    else:
                        # j =0 if j==e-s-2 else j
                        continue
                else:
                    # j = e - s if j == (e - s - 2) else j
                    break  # j 就是右侧波谷

            # =========================================================
            # 现在连续的波段被分成了3段[s, s+i][s+i, s+j][s+j, e]
            # max_row_index 为波峰；s+i为波谷；s+j为波谷；
            df.at[max_row_index, tag_field] = WaveType.RED_TOP  # 打tag

            # 在下一个阶段中评估波峰波谷的变化度（是否是深V？）
            # 一段连续的区间里可以产生多个波峰，但是波谷可能是重合的，这就要评估是否是深V，合并波峰
            df.at[s + i, tag_field] = WaveType.RED_BOTTOM
            df.at[s + j, tag_field] = WaveType.RED_BOTTOM

            # 剩下两段加入sub_area_list继续迭代
            if s != s+i:
                sub_area_list.append((s, s + i))
                print(f"++{s}-{s+i}", end=":")
            if s+j!=e and j!=0:  # j为啥不能为0呢？如果为0 说明循环进不去,由此推倒出极值点位于最左侧开始的2个位置，这个宽度不足以参与下一个遍历。
                sub_area_list.append((s + j, e))
                print(f"+{s+j}-{e}", end=":")


            print(f'||{s+i}-{s+j}')
        # 这里是一个连续区间处理完毕
        # 还需要对波谷、波峰进行合并，如果不是深V那么就合并掉
        # TODO

    return df


def __bar_wave_field_tag(df, field):
    """
    扫描一个字段的波谷波峰
    """
    blue_bar_area = find_successive_bar_areas(df, field)
    do_bar_wave_tag(df, field, blue_bar_area)
    return df


def __is_bar_divergence(df, field): # TODO 从哪个位置开始算背离？
    """
    field字段是否出现了底背离
    :param df:
    :param field:
    :return: 背离：1， 否则0
    """
    pass  # TODO


def __bar_wave_cnt(df, field='macd_bar'): # TODO 从哪个位置开始数浪？
    """
    在一段连续的绿柱子区间，当前的波峰是第几个
    :param df:
    :param field:
    :return:  波峰个数, 默认1
    """
    pass  # TODO


def __is_bar_multi_wave(df, field='ma_bar'):
    """
    2波段
    :param df:
    :param field:
    :return: 如果是第2个波段，或者2个以上返回1，否则返回0
    """
    wave_cnt = __bar_wave_cnt(df, field)
    rtn = 1 if wave_cnt >= 2 else 0
    return rtn


def __is_macd_bar_reduce(df:DataFrame, field='macd_bar'):
    """
    macd 绿柱子第一根减少出现，不能减少太剧烈，前面的绿色柱子不能太少
    :param df:
    :param field:
    :return:
    """
    cur_bar_len = df.iloc[-1][field]
    pre_bar_len = df.iloc[-2][field]

    is_reduce = cur_bar_len > pre_bar_len # TODO 这里还需要评估一下到底减少多少幅度/速度是最优的
    return is_reduce


def macd_strategy(code_list):
    """
    策略入口
    :return:
    """
    ok_code = {}
    for code in code_list:
        total_score = 0

        df60 = pd.read_csv(df_file_name(code, KL_Period.KL_60), index_col=0)
        if __is_macd_bar_reduce(df60, "macd_bar") == 1:  # 如果60分绿柱变短
            total_score += 1  # 60分绿柱变短分数+1

            bar_60_order = __bar_wave_cnt(df60, 'macd_bar')  # 60分macd波段第几波？
            total_score += (bar_60_order) * 1  # 多一波就多一分
            ma_60_2wave = __is_bar_multi_wave(df60, 'ma_bar')
            total_score += ma_60_2wave * 1  # 60分均线两波下跌

            df30 = pd.read_csv(df_file_name(code, KL_Period.KL_30), index_col=0)
            bar_30_divergence = __is_bar_divergence(df30, 'macd_bar')  # 30分macd背离
            total_score += bar_30_divergence

            ma_30_2wave = __is_bar_multi_wave(df30, 'ma_bar')
            total_score += (ma_30_2wave + ma_60_2wave * ma_30_2wave) * 2

            df15 = pd.read_csv(df_file_name(code, KL_Period.KL_15), index_col=0)
            bar_15_divergence = __is_bar_divergence(df15, 'macd_bar')
            total_score += bar_15_divergence

            ma_15_2wave = __is_bar_multi_wave(df15, 'ma_bar')  # 15分钟2个波段
            total_score += (ma_15_2wave + ma_30_2wave * ma_15_2wave) * 2

            ok_code[code] = total_score

            return ok_code


if __name__ == '__main__':
    """
    df -> df 格式化统一 -> macd_bar, em5, em10 -> macd_bar, em_bar -> 
    macd_bar 判别, macd_wave_scan em_bar_wave_scan -> 按权重评分 
    """
    STOCK_CODE = 'SZ.002405'
    #prepare_csv_data([STOCK_CODE])
    compute_df_bar([STOCK_CODE])
    fname = df_file_name(STOCK_CODE, KLType.K_60M)
    df60 = pd.read_csv(fname, index_col=0)
    red_areas, blue_areas = find_successive_bar_areas(df60, 'macd_bar')
    df_new = do_bar_wave_tag(df60, 'macd_bar', red_areas)
    df_new
