"""Pure Plotly constructors. Charts contain ALL loaded bars, not a tail slice.

The viewport is changed by setting a date range; zooming and the range slider
operate on the complete provider-supplied history. No synthetic extrapolation.
"""
from __future__ import annotations
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from indicators import IndicatorSettings

WINDOWS = ('1M', '3M', '6M', '1Y', '2Y', '5Y', 'ALL')


def window_bounds(index, window: str):
    if window not in WINDOWS:
        raise ValueError('Unsupported date window.')
    if len(index) == 0:
        raise ValueError('Empty price history.')
    start, end = pd.Timestamp(index[0]), pd.Timestamp(index[-1])
    offsets = {'1M': pd.DateOffset(months=1), '3M': pd.DateOffset(months=3),
               '6M': pd.DateOffset(months=6), '1Y': pd.DateOffset(years=1),
               '2Y': pd.DateOffset(years=2), '5Y': pd.DateOffset(years=5)}
    first = max(start, end - offsets[window]) if window in offsets else start
    return first, end


def create_price_figure(frame: pd.DataFrame, settings: IndicatorSettings, *, window='6M',
                        candle=True, lower='RSI', overlays=('SMA','EMA'),
                        currency='', symbol='', mode='neutral') -> go.Figure:
    if frame.empty or not isinstance(frame.index, pd.DatetimeIndex):
        raise ValueError('Historical prices require a nonempty datetime-indexed frame.')
    if not frame.index.is_monotonic_increasing:
        frame = frame.sort_index()
    start, end = window_bounds(frame.index, window)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.09,
                        row_heights=[0.72, 0.28])
    colors = {'neutral':('#285EC5','#C87934'), 'us':('#178057','#BA4747'),
              'cn':('#C43D4B','#178057')}
    up, down = colors.get(mode, colors['neutral'])
    prices = frame[['Open','High','Low','Close']] if {'Open','High','Low','Close'} <= set(frame) else None
    if candle and prices is not None and prices.notna().all().all():
        fig.add_trace(go.Candlestick(x=frame.index,open=frame.Open,high=frame.High,
                         low=frame.Low,close=frame.Close, name='OHLC',
                         increasing_line_color=up,decreasing_line_color=down),row=1,col=1)
    else:
        fig.add_trace(go.Scatter(x=frame.index,y=frame.Close,mode='lines',
                             name='Close',line=dict(color='#5266C6',width=2)),row=1,col=1)
    if 'SMA' in overlays:
        for col,label,color in [('SMA_fast',f'SMA({settings.sma_fast})','#8899B9'),
                                 ('SMA_slow',f'SMA({settings.sma_slow})','#C09854')]:
            fig.add_trace(go.Scatter(x=frame.index,y=frame[col],name=label,
                        line=dict(color=color,width=1.7),connectgaps=False),row=1,col=1)
    if 'EMA' in overlays:
        fig.add_trace(go.Scatter(x=frame.index,y=frame.EMA,name=f'EMA({settings.ema_period})',
                          line=dict(color='#7E61C6',width=1.7)),row=1,col=1)
    if 'BB' in overlays:
        fig.add_trace(go.Scatter(x=frame.index,y=frame.BB_upper,name='BB upper',
                          line=dict(color='#A1A9BD',dash='dot',width=1.2)),row=1,col=1)
        fig.add_trace(go.Scatter(x=frame.index,y=frame.BB_lower,name='BB lower',
                          line=dict(color='#A1A9BD',dash='dot',width=1.2),
                          fill='tonexty',fillcolor='rgba(80,100,160,.04)'),row=1,col=1)
    if lower == 'RSI':
        fig.add_trace(go.Scatter(x=frame.index,y=frame.RSI,name=f'RSI({settings.rsi_period})',
                                line=dict(color='#5266C6')),row=2,col=1)
        fig.add_hline(y=70,line_dash='dash',line_color='#BD8C46',opacity=.7,row=2,col=1)
        fig.add_hline(y=30,line_dash='dash',line_color='#5E89C6',opacity=.7,row=2,col=1)
        fig.update_yaxes(range=[0,100],row=2,col=1)
    elif lower == 'MACD':
        fig.add_trace(go.Bar(x=frame.index,y=frame.MACD_hist,name='Histogram',marker_color='#8C9ED0'),row=2,col=1)
        fig.add_trace(go.Scatter(x=frame.index,y=frame.MACD,name='MACD',line=dict(color='#285EC5')),row=2,col=1)
        fig.add_trace(go.Scatter(x=frame.index,y=frame.MACD_signal,name='Signal',line=dict(color='#C87934')),row=2,col=1)
    elif lower == 'Volume':
        if 'Volume' in frame:
            fig.add_trace(go.Bar(x=frame.index,y=frame.Volume,name='Volume',marker_color='#8C9ED0'),row=2,col=1)
    elif lower == 'ATR':
        fig.add_trace(go.Scatter(x=frame.index,y=frame.ATR,name=f'ATR({settings.atr_period})',
                                  line=dict(color='#5266C6')),row=2,col=1)
    elif lower == 'KDJ':
        for field,color in [('K','#285EC5'),('D','#C87934'),('J','#7E61C6')]:
            fig.add_trace(go.Scatter(x=frame.index,y=frame[field],name=field,line=dict(color=color)),row=2,col=1)
    else:
        raise ValueError('Unsupported lower indicator.')
    fig.update_layout(template='plotly_white',height=660,autosize=True,
                      margin=dict(l=12,r=20,t=48,b=22),
                      paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='#FFFFFF',
                      hovermode='x unified',legend=dict(orientation='h',y=1.12,x=0),
                      uirevision=f'{symbol}:{window}:{candle}:{lower}:{settings}:{overlays}')
    # This is the key fix: data arrays are complete, viewport is only a range.
    # minallowed/maxallowed prevent zooming beyond downloaded history.
    for row in (1,2):
        fig.update_xaxes(type='date',range=[start,end],minallowed=frame.index[0],
                         maxallowed=frame.index[-1],showgrid=True,gridcolor='#EDF1F6',
                         rangeslider_visible=(row == 2),row=row,col=1)
    fig.update_yaxes(showgrid=True,gridcolor='#EDF1F6',row=1,col=1,title_text=currency)
    return fig
