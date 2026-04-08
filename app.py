"""
Chinook Analytics Dashboard
음악 스토어 경영분석 대시보드 (Streamlit + SQLite)

실행 방법:
    pip install -r requirements.txt
    streamlit run app.py
"""

import sqlite3
import os
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

# ============================================================
# 페이지 기본 설정
# ============================================================
st.set_page_config(
    page_title="Chinook Analytics",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded",
)

PLOTLY_FONT = dict(
    family="Noto Sans KR, Malgun Gothic, AppleGothic, sans-serif",
    size=12,
)

COLOR_PALETTE = ["#2563eb", "#7c3aed", "#f59e0b", "#10b981", "#ef4444",
                 "#06b6d4", "#ec4899", "#84cc16", "#f97316", "#6366f1"]

DB_PATH = "chinook.db"


# ============================================================
# 데이터 로딩 (캐싱)
# ============================================================
@st.cache_data(show_spinner=False)
def load_data():
    if not os.path.exists(DB_PATH):
        return None

    conn = sqlite3.connect(DB_PATH)
    try:
        invoices_query = """
            SELECT
                i.InvoiceId,
                i.CustomerId,
                i.InvoiceDate,
                i.BillingCountry AS Country,
                i.BillingCity AS City,
                i.Total,
                c.FirstName || ' ' || c.LastName AS CustomerName,
                c.SupportRepId,
                e.FirstName || ' ' || e.LastName AS SalesRep
            FROM invoices i
            LEFT JOIN customers c ON i.CustomerId = c.CustomerId
            LEFT JOIN employees e ON c.SupportRepId = e.EmployeeId
        """
        df_invoices = pd.read_sql(invoices_query, conn)
        df_invoices["InvoiceDate"] = pd.to_datetime(df_invoices["InvoiceDate"])
        df_invoices["Year"] = df_invoices["InvoiceDate"].dt.year
        df_invoices["Month"] = df_invoices["InvoiceDate"].dt.month
        df_invoices["YearMonth"] = df_invoices["InvoiceDate"].dt.to_period("M").astype(str)

        items_query = """
            SELECT
                ii.InvoiceLineId,
                ii.InvoiceId,
                ii.TrackId,
                ii.UnitPrice,
                ii.Quantity,
                (ii.UnitPrice * ii.Quantity) AS LineTotal,
                t.Name AS TrackName,
                t.GenreId,
                g.Name AS Genre,
                t.AlbumId,
                al.Title AS Album,
                al.ArtistId,
                ar.Name AS Artist,
                i.InvoiceDate,
                i.BillingCountry AS Country
            FROM invoice_items ii
            LEFT JOIN tracks t ON ii.TrackId = t.TrackId
            LEFT JOIN genres g ON t.GenreId = g.GenreId
            LEFT JOIN albums al ON t.AlbumId = al.AlbumId
            LEFT JOIN artists ar ON al.ArtistId = ar.ArtistId
            LEFT JOIN invoices i ON ii.InvoiceId = i.InvoiceId
        """
        df_items = pd.read_sql(items_query, conn)
        df_items["InvoiceDate"] = pd.to_datetime(df_items["InvoiceDate"])
        df_items["Year"] = df_items["InvoiceDate"].dt.year

        return {"invoices": df_invoices, "items": df_items}
    finally:
        conn.close()


# ============================================================
# 유틸리티 함수
# ============================================================
def apply_filters(df, year_range, countries):
    mask = (df["Year"] >= year_range[0]) & (df["Year"] <= year_range[1])
    if countries:
        mask &= df["Country"].isin(countries)
    return df[mask].copy()


def style_plotly(fig, height=400):
    fig.update_layout(
        font=PLOTLY_FONT,
        height=height,
        margin=dict(l=20, r=20, t=50, b=20),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        hoverlabel=dict(font_family=PLOTLY_FONT["family"]),
    )
    return fig


def format_currency(value):
    return f"${value:,.2f}"


# ============================================================
# 페이지 1: 매출 Overview
# ============================================================
def page_overview(df_inv, df_inv_full):
    st.title("📊 매출 Overview")
    st.caption("전체 매출 추이와 핵심 지표를 한눈에 확인합니다.")

    if df_inv.empty:
        st.warning("선택한 조건에 해당하는 데이터가 없습니다. 사이드바 필터를 조정해주세요.")
        return

    total_revenue = df_inv["Total"].sum()
    total_orders = len(df_inv)
    total_customers = df_inv["CustomerId"].nunique()
    avg_order = total_revenue / total_orders if total_orders > 0 else 0

    full_revenue = df_inv_full["Total"].sum()
    full_orders = len(df_inv_full)
    full_customers = df_inv_full["CustomerId"].nunique()
    full_avg = full_revenue / full_orders if full_orders > 0 else 0

    delta_revenue = total_revenue - full_revenue
    delta_orders = total_orders - full_orders
    delta_customers = total_customers - full_customers
    delta_avg = avg_order - full_avg

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("총 매출", format_currency(total_revenue),
                  delta=f"{delta_revenue:+,.2f}" if delta_revenue != 0 else None)
    with col2:
        st.metric("총 주문수", f"{total_orders:,}",
                  delta=f"{delta_orders:+,}" if delta_orders != 0 else None)
    with col3:
        st.metric("고객수", f"{total_customers:,}",
                  delta=f"{delta_customers:+,}" if delta_customers != 0 else None)
    with col4:
        st.metric("평균 주문액", format_currency(avg_order),
                  delta=f"{delta_avg:+,.2f}" if delta_avg != 0 else None)

    st.markdown("---")

    st.subheader("📈 연도별 매출 추이")
    yearly = df_inv.groupby("Year").agg(
        Revenue=("Total", "sum"),
        Orders=("InvoiceId", "count"),
    ).reset_index()

    fig_line = go.Figure()
    fig_line.add_trace(go.Scatter(
        x=yearly["Year"], y=yearly["Revenue"],
        mode="lines+markers+text",
        name="매출",
        line=dict(color=COLOR_PALETTE[0], width=3),
        marker=dict(size=10),
        text=[format_currency(v) for v in yearly["Revenue"]],
        textposition="top center",
        hovertemplate="<b>%{x}</b><br>매출: $%{y:,.2f}<extra></extra>",
    ))
    fig_line.update_layout(title="연도별 매출", xaxis_title="연도", yaxis_title="매출 ($)", xaxis=dict(dtick=1))
    st.plotly_chart(style_plotly(fig_line, height=380), use_container_width=True)

    st.subheader("🔥 월별 매출 히트맵")
    heatmap = df_inv.groupby(["Year", "Month"])["Total"].sum().reset_index()
    pivot = heatmap.pivot(index="Year", columns="Month", values="Total").fillna(0)
    for m in range(1, 13):
        if m not in pivot.columns:
            pivot[m] = 0
    pivot = pivot[sorted(pivot.columns)]
    month_labels = [f"{m}월" for m in pivot.columns]

    fig_heat = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=month_labels,
        y=pivot.index,
        colorscale="Blues",
        text=[[f"${v:.0f}" if v > 0 else "" for v in row] for row in pivot.values],
        texttemplate="%{text}",
        textfont={"size": 10},
        hovertemplate="<b>%{y}년 %{x}</b><br>매출: $%{z:,.2f}<extra></extra>",
        colorbar=dict(title="매출 ($)"),
    ))
    fig_heat.update_layout(title="연도 × 월 매출 히트맵", xaxis_title="월", yaxis_title="연도", yaxis=dict(dtick=1))
    st.plotly_chart(style_plotly(fig_heat, height=350), use_container_width=True)


# ============================================================
# 페이지 2: 고객 & 지역 분석
# ============================================================
def page_customers(df_inv):
    st.title("🌍 고객 & 지역 분석")
    st.caption("국가별 매출과 고객별 구매 패턴을 분석합니다.")

    if df_inv.empty:
        st.warning("선택한 조건에 해당하는 데이터가 없습니다.")
        return

    st.subheader("🏆 국가별 매출 Top 10")
    country_rev = df_inv.groupby("Country").agg(
        Revenue=("Total", "sum"),
        Orders=("InvoiceId", "count"),
        Customers=("CustomerId", "nunique"),
    ).reset_index().sort_values("Revenue", ascending=False).head(10)

    fig_country = px.bar(
        country_rev.sort_values("Revenue"),
        x="Revenue", y="Country",
        orientation="h",
        text=country_rev.sort_values("Revenue")["Revenue"].apply(lambda v: f"${v:,.0f}"),
        color="Revenue",
        color_continuous_scale="Blues",
    )
    fig_country.update_traces(textposition="outside")
    fig_country.update_layout(xaxis_title="매출 ($)", yaxis_title="", coloraxis_showscale=False)
    st.plotly_chart(style_plotly(fig_country, height=420), use_container_width=True)

    st.subheader("💎 국가별 고객 수 vs 평균 주문액")
    scatter = df_inv.groupby("Country").agg(
        Customers=("CustomerId", "nunique"),
        AvgOrder=("Total", "mean"),
        TotalRevenue=("Total", "sum"),
    ).reset_index()

    fig_scatter = px.scatter(
        scatter, x="Customers", y="AvgOrder",
        size="TotalRevenue", color="TotalRevenue",
        hover_name="Country", text="Country",
        color_continuous_scale="Viridis", size_max=50,
        labels={"Customers": "고객 수", "AvgOrder": "평균 주문액 ($)", "TotalRevenue": "총 매출 ($)"},
    )
    fig_scatter.update_traces(textposition="top center", textfont_size=10)
    st.plotly_chart(style_plotly(fig_scatter, height=450), use_container_width=True)

    st.subheader("👤 고객별 구매 순위")
    customer_rank = df_inv.groupby(["CustomerId", "CustomerName", "Country"]).agg(
        총주문수=("InvoiceId", "count"),
        총구매액=("Total", "sum"),
        평균주문액=("Total", "mean"),
    ).reset_index().sort_values("총구매액", ascending=False)

    customer_rank["총구매액"] = customer_rank["총구매액"].round(2)
    customer_rank["평균주문액"] = customer_rank["평균주문액"].round(2)
    customer_rank = customer_rank.rename(columns={"CustomerName": "고객명", "Country": "국가"})[
        ["고객명", "국가", "총주문수", "총구매액", "평균주문액"]
    ]

    search = st.text_input("🔍 고객명 또는 국가로 검색", placeholder="예: Smith, Germany...")
    if search:
        mask = (
            customer_rank["고객명"].str.contains(search, case=False, na=False)
            | customer_rank["국가"].str.contains(search, case=False, na=False)
        )
        customer_rank = customer_rank[mask]

    st.dataframe(
        customer_rank, use_container_width=True, height=400,
        column_config={
            "총구매액": st.column_config.NumberColumn(format="$%.2f"),
            "평균주문액": st.column_config.NumberColumn(format="$%.2f"),
        },
        hide_index=True,
    )
    st.caption(f"총 {len(customer_rank)}명의 고객")


# ============================================================
# 페이지 3: 장르 & 상품 분석
# ============================================================
def page_genres(df_items):
    st.title("🎵 장르 & 상품 분석")
    st.caption("음악 장르별 판매 트렌드와 인기 아티스트를 분석합니다.")

    if df_items.empty:
        st.warning("선택한 조건에 해당하는 데이터가 없습니다.")
        return

    col_a, col_b = st.columns([1, 1])

    with col_a:
        st.subheader("🍩 장르별 판매량 비중")
        genre_qty = df_items.groupby("Genre").agg(
            Quantity=("Quantity", "sum"),
            Revenue=("LineTotal", "sum"),
        ).reset_index().sort_values("Quantity", ascending=False)

        if len(genre_qty) > 8:
            top = genre_qty.head(8)
            others_qty = genre_qty.iloc[8:]["Quantity"].sum()
            others_rev = genre_qty.iloc[8:]["Revenue"].sum()
            top = pd.concat([top, pd.DataFrame([{"Genre": "기타", "Quantity": others_qty, "Revenue": others_rev}])], ignore_index=True)
        else:
            top = genre_qty

        fig_donut = go.Figure(data=[go.Pie(
            labels=top["Genre"], values=top["Quantity"], hole=0.5,
            marker=dict(colors=COLOR_PALETTE),
            textinfo="label+percent",
            hovertemplate="<b>%{label}</b><br>판매량: %{value}곡<br>비중: %{percent}<extra></extra>",
        )])
        fig_donut.update_layout(showlegend=True, legend=dict(orientation="v", x=1.0, y=0.5))
        st.plotly_chart(style_plotly(fig_donut, height=400), use_container_width=True)

    with col_b:
        st.subheader("📊 장르별 매출 요약")
        genre_summary = df_items.groupby("Genre").agg(
            판매량=("Quantity", "sum"),
            매출=("LineTotal", "sum"),
        ).reset_index().sort_values("매출", ascending=False).head(10)
        genre_summary["매출"] = genre_summary["매출"].round(2)
        st.dataframe(genre_summary, use_container_width=True, height=400,
                     column_config={"매출": st.column_config.NumberColumn(format="$%.2f")},
                     hide_index=True)

    st.subheader("📈 장르별 매출 트렌드 (Top 6)")
    top_genres = df_items.groupby("Genre")["LineTotal"].sum().nlargest(6).index.tolist()
    trend = df_items[df_items["Genre"].isin(top_genres)].groupby(["Year", "Genre"])["LineTotal"].sum().reset_index()

    fig_area = px.area(
        trend, x="Year", y="LineTotal", color="Genre",
        color_discrete_sequence=COLOR_PALETTE,
        labels={"LineTotal": "매출 ($)", "Year": "연도"},
    )
    fig_area.update_layout(xaxis=dict(dtick=1), hovermode="x unified")
    st.plotly_chart(style_plotly(fig_area, height=400), use_container_width=True)

    st.subheader("🎤 인기 아티스트 Top 15 (매출 기준)")
    artist_rev = df_items.groupby("Artist").agg(
        매출=("LineTotal", "sum"),
        판매량=("Quantity", "sum"),
    ).reset_index().sort_values("매출", ascending=False).head(15)

    fig_artist = px.bar(
        artist_rev.sort_values("매출"),
        x="매출", y="Artist", orientation="h",
        text=artist_rev.sort_values("매출")["매출"].apply(lambda v: f"${v:.2f}"),
        color="매출", color_continuous_scale="Purples",
    )
    fig_artist.update_traces(textposition="outside")
    fig_artist.update_layout(xaxis_title="매출 ($)", yaxis_title="", coloraxis_showscale=False)
    st.plotly_chart(style_plotly(fig_artist, height=500), use_container_width=True)


# ============================================================
# 페이지 4: 영업사원 성과
# ============================================================
def page_sales_rep(df_inv):
    st.title("👤 영업사원 성과")
    st.caption("Sales Support Agent별 성과를 비교 분석합니다.")

    if df_inv.empty:
        st.warning("선택한 조건에 해당하는 데이터가 없습니다.")
        return

    df_rep = df_inv[df_inv["SalesRep"].notna()].copy()
    if df_rep.empty:
        st.warning("영업사원 정보가 있는 데이터가 없습니다.")
        return

    rep_summary = df_rep.groupby("SalesRep").agg(
        매출=("Total", "sum"),
        주문수=("InvoiceId", "count"),
        고객수=("CustomerId", "nunique"),
    ).reset_index().sort_values("매출", ascending=False)

    cols = st.columns(len(rep_summary))
    for idx, (col, row) in enumerate(zip(cols, rep_summary.itertuples())):
        with col:
            st.metric(row.SalesRep, format_currency(row.매출),
                      delta=f"{row.주문수}건 / {row.고객수}명", delta_color="off")

    st.markdown("---")

    st.subheader("📊 담당자별 성과 비교")
    fig_compare = go.Figure()
    fig_compare.add_trace(go.Bar(
        name="매출 ($)", x=rep_summary["SalesRep"], y=rep_summary["매출"],
        marker_color=COLOR_PALETTE[0],
        text=[f"${v:.0f}" for v in rep_summary["매출"]],
        textposition="outside", yaxis="y",
    ))
    fig_compare.add_trace(go.Bar(
        name="주문수", x=rep_summary["SalesRep"], y=rep_summary["주문수"],
        marker_color=COLOR_PALETTE[1], text=rep_summary["주문수"],
        textposition="outside", yaxis="y2",
    ))
    fig_compare.add_trace(go.Bar(
        name="고객수", x=rep_summary["SalesRep"], y=rep_summary["고객수"],
        marker_color=COLOR_PALETTE[2], text=rep_summary["고객수"],
        textposition="outside", yaxis="y2",
    ))
    fig_compare.update_layout(
        barmode="group",
        yaxis=dict(title="매출 ($)", side="left"),
        yaxis2=dict(title="건수 / 명", side="right", overlaying="y"),
        legend=dict(orientation="h", y=1.12, x=0.5, xanchor="center"),
    )
    st.plotly_chart(style_plotly(fig_compare, height=420), use_container_width=True)

    st.subheader("📈 담당자별 월별 매출 추이")
    monthly = df_rep.groupby(["YearMonth", "SalesRep"])["Total"].sum().reset_index()
    monthly = monthly.sort_values("YearMonth")

    fig_monthly = px.line(
        monthly, x="YearMonth", y="Total", color="SalesRep",
        markers=True, color_discrete_sequence=COLOR_PALETTE,
        labels={"Total": "매출 ($)", "YearMonth": "연-월", "SalesRep": "담당자"},
    )
    fig_monthly.update_layout(hovermode="x unified", xaxis=dict(tickangle=-45))
    st.plotly_chart(style_plotly(fig_monthly, height=400), use_container_width=True)

    st.subheader("🌐 담당자별 고객 국가 분포")
    country_dist = df_rep.groupby(["SalesRep", "Country"]).agg(
        매출=("Total", "sum"),
        고객수=("CustomerId", "nunique"),
    ).reset_index()

    fig_dist = px.sunburst(
        country_dist, path=["SalesRep", "Country"],
        values="매출", color="매출", color_continuous_scale="Blues",
    )
    st.plotly_chart(style_plotly(fig_dist, height=500), use_container_width=True)

# ----------------------------------------------------------
    # 탭 3: 신규 고객 추가
    # ----------------------------------------------------------
    with tab3:
        st.subheader("➕ 신규 고객 추가")
        st.info("📌 이름, 성, 이메일은 필수 입력 항목입니다.")
 
        col1, col2 = st.columns(2)
        with col1:
            add_first = st.text_input("이름 (FirstName) *", placeholder="예: 민준")
            add_company = st.text_input("회사 (Company)", placeholder="예: (주)클로드")
            add_city = st.text_input("도시 (City)", placeholder="예: Seoul")
            add_country = st.text_input("국가 (Country)", placeholder="예: South Korea")
            add_phone = st.text_input("전화번호 (Phone)", placeholder="예: +82-10-0000-0000")
        with col2:
            add_last = st.text_input("성 (LastName) *", placeholder="예: 김")
            add_address = st.text_input("주소 (Address)", placeholder="예: 강남구 테헤란로 123")
            add_state = st.text_input("주/도 (State)", placeholder="예: Seoul")
            add_postal = st.text_input("우편번호 (PostalCode)", placeholder="예: 06234")
            add_email = st.text_input("이메일 (Email) *", placeholder="예: minjun@example.com")
 
        # 담당 직원 선택
        conn = sqlite3.connect(DB_PATH)
        df_emp = pd.read_sql(
            "SELECT EmployeeId, FirstName || ' ' || LastName AS Name FROM employees ORDER BY EmployeeId",
            conn
        )
        conn.close()
 
        emp_options = {"없음": None}
        emp_options.update({f"[{r.EmployeeId}] {r.Name}": r.EmployeeId for r in df_emp.itertuples()})
        selected_emp_label = st.selectbox("담당 직원 (선택)", list(emp_options.keys()))
        selected_emp_id = emp_options[selected_emp_label]
 
        st.markdown("---")
 
        # 미리보기
        with st.expander("👀 입력 내용 미리보기"):
            preview = {
                "이름": f"{add_first} {add_last}",
                "이메일": add_email,
                "회사": add_company or "-",
                "주소": f"{add_address}, {add_city}, {add_country}",
                "전화번호": add_phone or "-",
            }
            for k, v in preview.items():
                st.write(f"**{k}:** {v}")
 
        if st.button("➕ 고객 추가", type="primary", key="add_btn"):
            if not add_first.strip() or not add_last.strip() or not add_email.strip():
                st.error("⚠️ 이름, 성, 이메일은 필수 입력값입니다.")
            else:
                try:
                    conn = sqlite3.connect(DB_PATH)
                    conn.execute("""
                        INSERT INTO customers
                            (FirstName, LastName, Company, Address, City, State,
                             Country, PostalCode, Phone, Fax, Email, SupportRepId)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
                    """, (
                        add_first, add_last,
                        add_company or None, add_address or None,
                        add_city or None, add_state or None,
                        add_country or None, add_postal or None,
                        add_phone or None, add_email,
                        selected_emp_id
                    ))
                    conn.commit()
 
                    # 새로 생성된 ID 확인
                    new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                    conn.close()
 
                    st.success(f"✅ 신규 고객이 추가되었습니다! (고객 ID: {new_id})")
                    st.balloons()
                    st.cache_data.clear()
                except Exception as e:
                    st.error(f"❌ 추가 실패: {e}")
 
    # ----------------------------------------------------------
    # 탭 4: 고객 삭제
    # ----------------------------------------------------------
    with tab4:
        st.subheader("🗑️ 고객 삭제")
        st.warning("⚠️ 삭제된 고객 정보는 복구할 수 없습니다. 신중하게 진행해주세요.")
 
        conn = sqlite3.connect(DB_PATH)
        df_del_list = pd.read_sql(
            "SELECT CustomerId, FirstName || ' ' || LastName AS FullName, Email, Country FROM customers ORDER BY CustomerId",
            conn
        )
        conn.close()
 
        # 검색으로 좁히기
        del_search = st.text_input("🔍 삭제할 고객 검색 (이름 / 이메일)", placeholder="검색어를 입력하세요...")
        filtered_del = df_del_list.copy()
        if del_search:
            filtered_del = filtered_del[
                filtered_del["FullName"].str.contains(del_search, case=False, na=False)
                | filtered_del["Email"].str.contains(del_search, case=False, na=False)
            ]
 
        if filtered_del.empty:
            st.info("검색 결과가 없습니다.")
        else:
            del_options = {f"[{r.CustomerId}] {r.FullName} ({r.Email}) - {r.Country}": r.CustomerId
                           for r in filtered_del.itertuples()}
            selected_del_label = st.selectbox("삭제할 고객 선택", list(del_options.keys()))
            selected_del_id = del_options[selected_del_label]
 
            # 선택된 고객 정보 미리보기
            conn = sqlite3.connect(DB_PATH)
            del_row = pd.read_sql(
                "SELECT * FROM customers WHERE CustomerId = ?", conn, params=(selected_del_id,)
            ).iloc[0]
 
            # 구매 이력 확인
            purchase_count = pd.read_sql(
                "SELECT COUNT(*) AS cnt FROM invoices WHERE CustomerId = ?", conn, params=(selected_del_id,)
            ).iloc[0]["cnt"]
            conn.close()
 
            # 고객 정보 카드
            with st.expander("📄 선택된 고객 정보 확인", expanded=True):
                c1, c2 = st.columns(2)
                with c1:
                    st.write(f"**고객 ID:** {del_row['CustomerId']}")
                    st.write(f"**이름:** {del_row['FirstName']} {del_row['LastName']}")
                    st.write(f"**이메일:** {del_row['Email']}")
                    st.write(f"**회사:** {del_row['Company'] or '-'}")
                with c2:
                    st.write(f"**국가:** {del_row['Country'] or '-'}")
                    st.write(f"**도시:** {del_row['City'] or '-'}")
                    st.write(f"**전화번호:** {del_row['Phone'] or '-'}")
                    if purchase_count > 0:
                        st.error(f"🛒 구매 이력 {purchase_count}건 있음 — 삭제 시 관련 데이터도 함께 삭제됩니다!")
                    else:
                        st.success("🛒 구매 이력 없음")
 
            # 확인 체크박스 (실수 방지)
            confirm = st.checkbox(f"**[{selected_del_id}] {del_row['FirstName']} {del_row['LastName']}** 고객을 삭제하겠습니다.")
 
            if st.button("🗑️ 삭제 실행", type="primary", key="delete_btn", disabled=not confirm):
                try:
                    conn = sqlite3.connect(DB_PATH)
                    # 구매 이력이 있으면 관련 invoice_items → invoices 순으로 먼저 삭제
                    if purchase_count > 0:
                        conn.execute("""
                            DELETE FROM invoice_items
                            WHERE InvoiceId IN (
                                SELECT InvoiceId FROM invoices WHERE CustomerId = ?
                            )
                        """, (selected_del_id,))
                        conn.execute("DELETE FROM invoices WHERE CustomerId = ?", (selected_del_id,))
                    conn.execute("DELETE FROM customers WHERE CustomerId = ?", (selected_del_id,))
                    conn.commit()
                    conn.close()
                    st.success(f"✅ [{selected_del_id}] {del_row['FirstName']} {del_row['LastName']} 고객이 삭제되었습니다.")
                    st.cache_data.clear()
                except Exception as e:
                    st.error(f"❌ 삭제 실패: {e}")
 


# ============================================================
# 메인
# ============================================================
def main():
    with st.spinner("데이터를 불러오는 중..."):
        data = load_data()

    if data is None:
        st.error(f"❌ DB 파일을 찾을 수 없습니다: `{DB_PATH}`")
        st.info("이 app.py와 같은 폴더에 `chinook.db` 파일을 두고 다시 실행해주세요.")
        st.stop()

    df_inv_full = data["invoices"]
    df_items_full = data["items"]

    # ============================================================
    # 사이드바
    # ============================================================
    st.sidebar.title("🎵 Chinook Analytics")
    st.sidebar.caption("음악 스토어 경영분석 대시보드")
    st.sidebar.markdown("---")

    page = st.sidebar.radio(
        "📑 페이지 선택",
        ["📊 매출 Overview", "🌍 고객 & 지역", "🎵 장르 & 상품", "👤 영업사원 성과", "👥 고객 관리"],
    )

    # 고객 관리 페이지는 공통 필터 불필요
    if page != "👥 고객 관리":
        st.sidebar.markdown("---")
        st.sidebar.subheader("🔍 공통 필터")

        min_year = int(df_inv_full["Year"].min())
        max_year = int(df_inv_full["Year"].max())
        year_range = st.sidebar.slider("연도 범위", min_value=min_year, max_value=max_year,
                                       value=(min_year, max_year), step=1)

        all_countries = sorted(df_inv_full["Country"].dropna().unique().tolist())
        countries = st.sidebar.multiselect("국가 선택 (전체 = 비워두기)", options=all_countries,
                                           default=[], placeholder="국가를 선택하세요")

        df_inv_filtered = apply_filters(df_inv_full, year_range, countries)
        df_items_filtered = apply_filters(df_items_full, year_range, countries)

        st.sidebar.markdown("---")
        st.sidebar.markdown(f"""
        **현재 선택**
        - 기간: {year_range[0]}~{year_range[1]}
        - 국가: {len(countries) if countries else '전체'}
        - 주문: {len(df_inv_filtered):,}건
        - 매출: {format_currency(df_inv_filtered['Total'].sum())}
        """)
    else:
        df_inv_filtered = df_inv_full
        df_items_filtered = df_items_full

    # ============================================================
    # 페이지 라우팅
    # ============================================================
    if page == "📊 매출 Overview":
        page_overview(df_inv_filtered, df_inv_full)
    elif page == "🌍 고객 & 지역":
        page_customers(df_inv_filtered)
    elif page == "🎵 장르 & 상품":
        page_genres(df_items_filtered)
    elif page == "👤 영업사원 성과":
        page_sales_rep(df_inv_filtered)
    elif page == "👥 고객 관리":
        page_customer_management()

    st.markdown("---")
    st.caption("📚 Chinook Sample Database | Built with Streamlit + Plotly")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error(f"⚠️ 오류가 발생했습니다: {e}")
        st.exception(e)
