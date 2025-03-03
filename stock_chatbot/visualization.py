import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

def plot_stock_plotly(df, company, period):
    """
    Args:
        df (DataFrame): 주식 데이터
        company (str): 기업명
        period (str): 기간("1day", "week", "1month", "1year")
    """
    if df is None or df.empty:
        st.warning(f"📉 {company} - 해당 기간({period})의 거래 데이터가 없습니다.")
        return

    fig = go.Figure()

    # 🔹 데이터 컬럼명 확인 후 올바르게 매핑
    if "시간" in df.columns:
        df["FormattedDate"] = df["시간"].dt.strftime("%H:%M") if period == "1day" else df["시간"].dt.strftime("%m-%d %H:%M")
    elif "Date" in df.columns:
        df["FormattedDate"] = df["Date"].dt.strftime("%H:%M") if period == "1day" else df["Date"].dt.strftime("%m-%d %H:%M")
    else:
        st.error("📛 데이터에 '시간' 또는 'Date' 컬럼이 없습니다.")
        return

    # x축 간격 설정
    if period == "1day":
        tickvals = df.iloc[::60]["FormattedDate"].tolist()  # 1시간 간격
    elif period == "week":
        tickvals = df[df["FormattedDate"].str.endswith("09:00")]["FormattedDate"].tolist()  # 9시만 표시
    elif period == "1month":
        tickvals = df.iloc[::4]["FormattedDate"].tolist()  # 4일 간격
    else:
        df['Year'] = df["시간"].dt.year if "시간" in df.columns else df["Date"].dt.year
        df['Month'] = df["시간"].dt.month if "시간" in df.columns else df["Date"].dt.month

        # 첫 번째 월 구하기
        first_month = df['Month'].iloc[0]
        first_year = df['Year'].iloc[0]

        # 각 월의 첫 거래일 찾기 (첫 번째 월은 제외)
        monthly_data = []
        for (year, month), group in df.groupby(['Year', 'Month']):
            if year == first_year and month == first_month:
                continue
            first_day = group.iloc[0]
            monthly_data.append(first_day)

        # 최종 tickvals 계산
        if monthly_data:
            monthly_df = pd.DataFrame(monthly_data)
            tickvals = monthly_df["FormattedDate"].tolist()
        else:
            tickvals = []

    # 🔹 1day와 week는 선 그래프, 1month와 1year는 캔들 차트 적용
    if period in ["1day", "week"]:
        fig.add_trace(go.Scatter(
            x=df["FormattedDate"],
            y=df["종가"],
            mode="lines",
            name="종가"
        ))
    else:
        fig.add_trace(go.Candlestick(
            x=df["FormattedDate"],
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name="캔들 차트"
        ))

    fig.update_layout(
        title=f"{company} 주가 ({period})",
        xaxis_title="시간" if period == "1day" else "날짜",
        yaxis_title="주가 (KRW)",
        template="plotly_white",
        xaxis=dict(
            showgrid=True,
            type="category",
            tickmode='array',
            tickvals=tickvals,
            tickangle=-45
        ),
        hovermode="x unified"
    )

    st.plotly_chart(fig)