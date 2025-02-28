import plotly.graph_objects as go
import streamlit as st
import pandas as pd


def plot_stock_plotly(df, company, period):
    """
    Plotly를 이용한 주가 시각화 함수

    Args:
        df (DataFrame): 주식 데이터
        company (str): 기업명
        period (str): 기간("1day", "week", "1month", "1year")
    """
    if df is None or df.empty:
        st.warning(f"📉 {company} - 해당 기간({period})의 거래 데이터가 없습니다.")
        return

    fig = go.Figure()

    # x축 날짜 형식 설정
    if period == "1day":
        df["FormattedDate"] = df["Date"].dt.strftime("%H:%M")
    elif period == "week":
        df["FormattedDate"] = df["Date"].dt.strftime("%m-%d %H:%M")
    else:
        df["FormattedDate"] = df["Date"].dt.strftime("%m-%d")

    # x축 간격 설정
    if period == "1day":
        tickvals = df.iloc[::60]["FormattedDate"].tolist()  # 1시간 간격
    elif period == "week":
        tickvals = df[df["FormattedDate"].str.endswith("09:00")]["FormattedDate"].tolist()  # 9시만 표시
    elif period == "1month":
        tickvals = df.iloc[::4]["FormattedDate"].tolist()  # 4일 간격
    else:  # 1year - 첫 달은 건너뛰고 나머지 월만 표시
        df['Year'] = df['Date'].dt.year
        df['Month'] = df['Date'].dt.month

        # 첫 번째 월 구하기
        first_month = df['Month'].iloc[0]
        first_year = df['Year'].iloc[0]

        # 각 월의 첫 거래일 찾기 (첫 번째 월은 제외)
        monthly_data = []
        for (year, month), group in df.groupby(['Year', 'Month']):
            # 첫 번째 월 데이터는 건너뛰기
            if year == first_year and month == first_month:
                continue

            # 월별 첫 날짜 선택
            first_day = group.iloc[0]
            monthly_data.append(first_day)

        # 최종 tickvals 계산
        if monthly_data:
            monthly_df = pd.DataFrame(monthly_data)
            tickvals = monthly_df["FormattedDate"].tolist()
        else:
            tickvals = []

    # 모든 기간에서 캔들 차트 적용
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